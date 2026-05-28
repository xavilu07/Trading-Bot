# Backtest Runner Summary

- Generated at: 2026-05-28T15:17:42+00:00
- Mode: shadow
- Trades loaded: 45

| Layer | Evaluated | Accepted | Rejected | Total R | WR | Avg R | PF | Max DD | Delta R | Confidence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| raw_strategy | 45 | 45 | 0 | -5.5754 | 31.11% | -0.1239 | 0.7928 | -9.4942 | 0.0 | HIGH |
| public_safety_policy | 45 | 0 | 45 | 0 | 0.0% | 0.0 | 0.0 | 0.0 | 5.5754 | LOW |
| public_short_canary | 45 | 0 | 45 | 0 | 0.0% | 0.0 | 0.0 | 0.0 | 5.5754 | LOW |
| protection_engine_shadow | 45 | 21 | 24 | 2.5891 | 33.33% | 0.1233 | 1.2324 | -3.8844 | 8.1645 | MEDIUM |
| pair_universe_filter_shadow | 45 | 39 | 6 | -2.0979 | 33.33% | -0.0538 | 0.9065 | -8.5782 | 3.4775 | HIGH |
| kill_switch_risk_guard | 45 | 5 | 40 | 2.912 | 40.0% | 0.5824 | 1.9707 | -2.0 | 8.4874 | LOW |

## Contexts que más mejoran/empeoran

### raw_strategy
- Mejoran: sin datos
- Empeoran: sin datos
### public_safety_policy
- Mejoran: direction:short (10.8004R, n=22), session:NEW_YORK (8.4083R, n=14), trade_location:premium_zone (6.5896R, n=8)
- Empeoran: direction:long (5.225R, n=23), session:LONDON (3.084R, n=14), market_regime:TRENDING (2.5167R, n=15)
### public_short_canary
- Mejoran: direction:short (10.8004R, n=22), session:NEW_YORK (8.4083R, n=14), trade_location:premium_zone (6.5896R, n=8)
- Empeoran: direction:long (5.225R, n=23), session:LONDON (3.084R, n=14), market_regime:TRENDING (2.5167R, n=15)
### protection_engine_shadow
- Mejoran: direction:short (9.4775R, n=10), session:NEW_YORK (8.4083R, n=14), trade_location:premium_zone (6.5896R, n=8)
- Empeoran: session:LONDON (3.0225R, n=4), direction:long (1.313R, n=14), trade_location:discount_zone (0.5225R, n=2)
### pair_universe_filter_shadow
- Mejoran: setup_type:SECONDARY_SIGNAL (4.4775R, n=5), entry_context:BREAKOUT (3.4775R, n=6), direction:long (3.0R, n=5)
- Empeoran: setup_type:MAIN_SIGNAL (1.0R, n=1), session:LONDON (0.5225R, n=2), trade_location:discount_zone (0.5225R, n=2)
### kill_switch_risk_guard
- Mejoran: direction:short (9.8004R, n=21), session:NEW_YORK (8.4083R, n=14), trade_location:premium_zone (6.5896R, n=8)
- Empeoran: session:LONDON (5.084R, n=12), direction:long (1.313R, n=19), trade_location:near_resistance (1.1323R, n=7)
