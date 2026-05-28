# Public Safety Relaxation Shadow

## Objetivo

Evaluar una variante de política pública menos restrictiva sin tocar producción.

La política actual (`public_safety_policy`) sigue siendo la única usada por el runtime de publicación. La variante `relaxed_public_safety_v2` se ejecuta solo en backtests offline para medir impacto histórico.

## Política Actual

La política pública actual bloquea, entre otros casos:

- `market_regime=RANGING` o distinto de `TRENDING`.
- `entry_context=CHOPPY_RANGE`.
- `trade_location=premium_zone`.
- `setup_type=SECONDARY_SIGNAL`.
- `direction=short` en shadow mode, salvo canary explícito.
- `against_htf`, `low_volume`, `dirty_sideways_market`.
- Meta filter negativo, capital preservation, `trade_quality=TRASH`.
- Kill switch activo.
- Edge Activation Mode si no cumple `TRENDING + OVERLAP + LONG`.

Esto protege el canal público, pero puede rechazar demasiadas señales históricamente rentables.

## Variante Shadow `relaxed_public_safety_v2`

Reglas principales:

- Permite más `SHORT` solo si existe edge histórico favorable.
- Mantiene bloqueado `HIGH_VOLATILITY_LONG`.
- Mantiene bloqueados contextos con muestra suficiente y edge negativo (`PF < 1` o `AvgR < 0`).
- Bloquea `risk_plan_missing` o `risk_plan_invalid`.
- Bloquea señales con RR explícito inferior a `1.5`.
- Bloquea `against_htf` salvo si el contexto tiene edge histórico demostrado.

## Integración

El Backtest Runner compara:

- `raw_strategy`
- `public_safety_policy`
- `relaxed_public_safety_v2`
- `public_short_canary`
- `protection_engine_shadow`
- `pair_universe_filter_shadow`
- `kill_switch_risk_guard`

La variante relajada no se importa desde Telegram, scheduler ni `publish_signal`.

## Ejecución

```bash
python scripts/run_backtest_runner.py --mode shadow --min-trades 1
```

Outputs:

- `reports/backtest_runner_report.json`
- `reports/backtest_runner_report.csv`
- `reports/backtest_runner_summary.md`

## Métricas Añadidas

- `delta_total_r_vs_current_policy`
- `delta_accepted_vs_current_policy`
- `top_allowed_contexts`
- `top_blocked_contexts`

## Estado

Shadow-only. No activa señales reales, no modifica el canal público y no cambia la estrategia base.
