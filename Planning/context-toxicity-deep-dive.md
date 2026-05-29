# Context Toxicity Deep Dive

## Objetivo

Investigar offline los contextos marcados como inestables por `Strategy Validation`:

- `entry_context=CHOPPY_RANGE`
- `market_regime=HIGH_VOLATILITY`
- `setup_type=UNKNOWN`
- `session=UNKNOWN`
- `trade_location=UNKNOWN`

La investigación es solo reporting. No modifica producción, Telegram, scheduler, live trading, public policy, penalties, canary ni strategy core.

## Comando

```bash
.venv/bin/python scripts/analyze_context_toxicity.py --min-trades 5
```

## Inputs

Usa los registros ya persistidos por el bot:

- `data/paper_trading/*.csv`
- `data/live_trading/trades.csv`
- `data/bot_activity/signals_log.jsonl`
- `reports/triple_barrier_labels.csv`
- `reports/meta_dataset.csv`

## Outputs

- `reports/context_toxicity_deep_dive.json`
- `reports/context_toxicity_deep_dive.csv`
- `reports/context_toxicity_deep_dive_summary.md`

## Segmentos

- Global
- London only
- Short only
- Long only
- High volatility long
- High volatility short
- Choppy range short
- Choppy range long

## Métricas

- Total R
- Profit factor
- Winrate
- Avg R
- Max drawdown
- Sample size
- Confidence
- Rolling last 10/20/30
- Degradation
- Toxicity score
- Opportunity score

## Interpretación

- `CONFIRMED_TOXIC`: contexto con muestra suficiente y rendimiento negativo.
- `HIDDEN_EDGE`: contexto con rendimiento positivo, especialmente si solo aparece bajo filtros como London o volumen alto.
- `UNSTABLE`: muestra insuficiente o resultados mixtos.

## Regla de Seguridad

Si `HIGH_VOLATILITY_LONG` sigue negativo, debe considerarse toxicidad confirmada. Si `HIGH_VOLATILITY_SHORT` o `CHOPPY_RANGE_SHORT` solo funcionan en London/volumen alto, se marcan como hidden edge, no como relajación global.
