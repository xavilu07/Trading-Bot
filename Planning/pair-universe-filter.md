# Pair Universe Filter

## Objetivo

Añadir una capa determinística para evaluar si un símbolo es apto para análisis antes de ejecutar la estrategia, inspirada en los filtros de pairlist/protections de Freqtrade.

La primera fase funciona en `shadow_only` por defecto: evalúa, loguea y resume qué pares habría excluido, pero no cambia la lista real de símbolos analizados.

## Ubicación

- Módulo: `src/trading_signals/market/pair_universe_filter.py`
- Integración: `src/trading_signals/application/use_cases/run_market_scan.py`
- Configuración: `src/trading_signals/app/settings.py`

## Modos

| Modo | Comportamiento |
|---|---|
| `disabled` | No falla símbolos. |
| `shadow_only` | Evalúa símbolos y loguea fallos, pero mantiene todos los símbolos válidos para análisis. |
| `enforce_paper` | Deja preparado enforcement para fases futuras; puede restringir `valid_symbols` a los pares que pasan el filtro. No es el valor por defecto. |

## Checks Evaluados

### Calidad de mercado

- Volumen mínimo.
- Spread estimado usando distancia `open-close` de la última vela.
- Volatilidad mínima y máxima usando rango `high-low` de la última vela.
- Histórico mínimo de velas.

### Configuración manual

- Blacklist configurable.
- Whitelist configurable.

### Señales recientes

- Símbolos con demasiados rechazos recientes en `data/bot_activity/signals_log.jsonl`.

### Performance reciente

- Símbolos con avgR reciente demasiado negativo en `data/paper_trading/*.csv` y `data/live_trading/trades.csv`.

## Variables de Entorno

```bash
PAIR_UNIVERSE_FILTER_MODE=shadow_only
PAIR_UNIVERSE_MIN_VOLUME=0
PAIR_UNIVERSE_MAX_SPREAD_PCT=5
PAIR_UNIVERSE_MIN_VOLATILITY_PCT=0.1
PAIR_UNIVERSE_MAX_VOLATILITY_PCT=25
PAIR_UNIVERSE_MIN_HISTORY_CANDLES=220
PAIR_UNIVERSE_BLACKLIST=
PAIR_UNIVERSE_WHITELIST=
PAIR_UNIVERSE_REJECTION_THRESHOLD=5
PAIR_UNIVERSE_REJECTION_LOOKBACK_HOURS=24
PAIR_UNIVERSE_MIN_RECENT_AVG_R=-0.5
PAIR_UNIVERSE_PERFORMANCE_MIN_TRADES=3
PAIR_UNIVERSE_PERFORMANCE_LOOKBACK_DAYS=14
```

## Logs

Cada símbolo genera un evento `pair_filter_evaluated`.

Si falla:

```json
{
  "event": "pair_filter_failed",
  "symbol": "DOGEUSDT",
  "mode": "shadow_only",
  "pair_filter_reason": "too_many_recent_rejections|recent_performance_too_negative",
  "metrics": {
    "history_candles": 300,
    "volume": 1000,
    "spread_pct": 0.2,
    "volatility_pct": 1.5,
    "recent_rejections": 6,
    "trades": 4,
    "avg_r": -0.8
  }
}
```

## Resumen en `run_market_scan`

El resultado del scan incluye:

```json
{
  "pair_universe_filter": {
    "mode": "shadow_only",
    "passed_symbols": ["BTCUSDT"],
    "failed_symbols": [],
    "excluded_if_enforced": [],
    "reason_counts": {},
    "impact_estimate": {
      "would_exclude": 0,
      "would_analyze": 1,
      "current_mode_keeps_all": true
    }
  }
}
```

## Estado Actual

La fase actual no cambia estrategia, señales, Telegram público ni live trading. Solo añade diagnósticos para medir el impacto antes de activar exclusión real.
