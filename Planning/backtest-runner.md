# Backtest Runner Consolidado

## Objetivo

El Backtest Runner consolidado compara capas del bot sobre resultados históricos reales ya registrados. No ejecuta la estrategia, no publica señales y no modifica producción.

## Comando

```bash
python scripts/run_backtest_runner.py --mode shadow --min-trades 1
```

## Entradas

- `data/paper_trading/*.csv`
- `data/live_trading/trades.csv`
- `data/bot_activity/signals_log.jsonl` si existe

Solo se usan trades con resultado real disponible (`result_r`, `r_result` o equivalente). No se inventan trades ni resultados.

## Capas comparadas

- `raw_strategy`: baseline con todos los trades reales cerrados.
- `public_safety_policy`: simula la política pública actual sin canary.
- `public_short_canary`: simula la política pública con canary SHORT habilitado de forma offline.
- `protection_engine_shadow`: simula protecciones tipo cooldown/drawdown/contexto tóxico usando solo trades anteriores.
- `pair_universe_filter_shadow`: simula exclusión por performance negativa reciente del símbolo y rechazos recientes.
- `kill_switch_risk_guard`: simula kill switch retrospectivo usando solo trades aceptados previamente.

## Outputs

- `reports/backtest_runner_report.json`
- `reports/backtest_runner_report.csv`
- `reports/backtest_runner_summary.md`

## Métricas

Por capa:

- trades evaluados
- trades aceptados
- trades rechazados
- total R
- winrate
- avg R
- profit factor
- max drawdown
- delta vs baseline
- sample size
- confidence
- top rejection reasons

## Interpretación

El runner mide impacto histórico de capas de control. Una mejora en `total_r` o `max_drawdown` no implica que deba activarse automáticamente en producción; sirve como evidencia para decidir qué validar después en shadow/canary.

## Restricciones

- No toca estrategia base.
- No toca Telegram.
- No toca scheduler.
- No toca live trading.
- No cambia configuración productiva.
- No activa canary ni filtros reales.
