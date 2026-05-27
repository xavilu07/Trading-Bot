# Protection Engine v2

## Objetivo

Añadir una capa determinística de protección inspirada en los mecanismos de protección de Freqtrade, sin modificar la estrategia base ni bloquear producción por defecto.

El motor se ejecuta en modo observacional (`shadow_only`) y emite diagnósticos para medir qué señales/candidatos habrían sido protegidos antes de decidir cualquier enforcement real.

## Ubicación

- Módulo: `src/trading_signals/risk/protection_engine.py`
- Integración: `src/trading_signals/application/use_cases/run_market_scan.py`
- Configuración: `src/trading_signals/app/settings.py`

## Modos

| Modo | Comportamiento |
|---|---|
| `disabled` | No evalúa protecciones ni genera triggers. |
| `shadow_only` | Evalúa y loguea protecciones, pero no bloquea publicación ni paper trading. Es el valor por defecto. |
| `enforce_paper` | Marca `protection_enforced=true` en el resultado. Reservado para una fase futura; la integración actual no bloquea producción. |

## Protecciones Iniciales

### Cooldown por símbolo tras pérdida

Activa `symbol_loss_cooldown` si el símbolo tuvo una pérdida reciente dentro de la ventana configurada.

Uso esperado:
- Evitar repetir entradas inmediatamente después de un SL.
- Mantener análisis en DEV/paper antes de bloquear real.

### Cooldown por símbolo tras rechazos repetidos

Activa `symbol_rejection_cooldown` si el símbolo acumula muchos `rejected` o `no_trade` en `data/bot_activity/signals_log.jsonl`.

Uso esperado:
- Detectar símbolos que están consumiendo ciclos sin producir setups válidos.
- Priorizar revisión de filtros/contexto.

### Max drawdown guard

Activa `max_drawdown_guard` si el R realizado agregado en la ventana reciente cae por debajo del límite.

Uso esperado:
- Complementar el kill switch actual con diagnóstico granular.
- Separar protección observacional de apagado real.

### Low-profit context lock

Activa `low_profit_context_lock` si una combinación de contexto tiene suficientes trades cerrados y avgR inferior al umbral.

Contexto evaluado:
- symbol
- direction
- setup_type
- market_regime
- session
- entry_context
- trade_location

### Toxic context guard

Activa `toxic_context_guard` para contextos marcados como peligrosos:
- `session=NEW_YORK`
- `market_regime=HIGH_VOLATILITY` + `direction=long`

Actualmente es diagnóstico configurable, no bloqueo real.

## Variables de Entorno

```bash
PROTECTION_ENGINE_MODE=shadow_only
PROTECTION_SYMBOL_LOSS_COOLDOWN_HOURS=6
PROTECTION_SYMBOL_REJECTION_THRESHOLD=3
PROTECTION_SYMBOL_REJECTION_LOOKBACK_HOURS=12
PROTECTION_SYMBOL_REJECTION_COOLDOWN_HOURS=6
PROTECTION_MAX_DRAWDOWN_GUARD_R=4.0
PROTECTION_MAX_DRAWDOWN_LOOKBACK_DAYS=7
PROTECTION_LOW_PROFIT_MIN_TRADES=5
PROTECTION_LOW_PROFIT_MIN_AVG_R=-0.2
PROTECTION_LOW_PROFIT_LOOKBACK_DAYS=14
PROTECTION_TOXIC_CONTEXT_SHADOW_ENABLED=true
```

## Logs

Cuando una protección dispara, se emite:

```json
{
  "event": "protection_triggered",
  "protection_triggered": true,
  "protection_reason": "symbol_loss_cooldown",
  "protection_mode": "shadow_only",
  "protection_enforced": false,
  "affected_symbol": "BTCUSDT",
  "affected_context": {
    "direction": "long",
    "setup_type": "MAIN_SIGNAL",
    "market_regime": "TRENDING",
    "session": "LONDON",
    "entry_context": "BREAKOUT",
    "trade_location": "mid_range"
  }
}
```

## Estado Actual

La Fase 1 no bloquea señales, no modifica Telegram público y no cambia paper/live tracking. Solo añade diagnósticos y deja preparado el enforcement controlado para fases futuras.
