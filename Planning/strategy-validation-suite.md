# Lookahead + Recursive Validation Suite

## Objetivo

Validar offline si el edge observado del bot podría depender de:

- Future leakage
- Lookahead bias
- Recalculation instability
- Candle close cheating
- Rolling contamination
- Hidden hindsight effects

La suite es solo research/offline. No modifica estrategia, filtros, Telegram, scheduler, live trading ni políticas públicas.

## Comando

```bash
.venv/bin/python scripts/run_strategy_validation.py --rolling-window 100 --delay-candles 1
```

## Inputs

Lee datos existentes si están disponibles:

- `data/paper_trading/*.csv`
- `data/live_trading/trades.csv`
- `data/bot_activity/signals_log.jsonl`
- `reports/triple_barrier_labels.csv`
- `reports/meta_dataset.csv`

## Outputs

- `reports/strategy_validation_report.json`
- `reports/strategy_validation_summary.md`
- `reports/strategy_validation_matrix.csv`

## Validaciones

- `lookahead_bias_detection`
- `recursive_recalculation_consistency`
- `rolling_window_validation`
- `candle_close_dependency_detection`
- `signal_timestamp_consistency`
- `delayed_entry_simulation`
- `indicator_recalculation_drift`
- `rolling_pf_stability`
- `rolling_wr_stability`
- `overfit_context_detection`

## Estados

- `SAFE`: no hay señal cuantitativa relevante.
- `WARNING`: revisar antes de tocar estrategia.
- `DANGEROUS`: no usar el edge para cambios productivos hasta investigar.

## Limitaciones

Si no hay velas OHLC completas, la suite no inventa resultados. Usa timestamps, resultados cerrados, triple barrier labels y registros persistidos. Las sospechas quedan marcadas como métricas de riesgo, no como prueba absoluta.
