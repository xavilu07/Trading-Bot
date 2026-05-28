# Backtest Runner Summary

- Generated at: 2026-05-28T15:28:25+00:00
- Mode: shadow
- Trades loaded: 45

| Layer | Evaluated | Accepted | Rejected | Total R | WR | Avg R | PF | Max DD | Delta R | Delta vs Current | Confidence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| raw_strategy | 45 | 45 | 0 | -5.5754 | 31.11% | -0.1239 | 0.7928 | -9.4942 | 0.0 | -5.5754 | HIGH |
| public_safety_policy | 45 | 0 | 45 | 0 | 0.0% | 0.0 | 0.0 | 0.0 | 5.5754 | 0.0 | LOW |
| relaxed_public_safety_v2 | 45 | 2 | 43 | 1.0 | 50.0% | 0.5 | 2.0 | -1.0 | 6.5754 | 1.0 | LOW |
| public_short_canary | 45 | 0 | 45 | 0 | 0.0% | 0.0 | 0.0 | 0.0 | 5.5754 | 0.0 | LOW |
| protection_engine_shadow | 45 | 21 | 24 | 2.5891 | 33.33% | 0.1233 | 1.2324 | -3.8844 | 8.1645 | 2.5891 | MEDIUM |
| pair_universe_filter_shadow | 45 | 39 | 6 | -2.0979 | 33.33% | -0.0538 | 0.9065 | -8.5782 | 3.4775 | -2.0979 | HIGH |
| kill_switch_risk_guard | 45 | 5 | 40 | 2.912 | 40.0% | 0.5824 | 1.9707 | -2.0 | 8.4874 | 2.912 | LOW |

## Contexts que más mejoran/empeoran

### raw_strategy
- Mejoran: sin datos
- Empeoran: sin datos
- Top allowed: direction:long (5.225R, n=23), session:LONDON (3.084R, n=14), market_regime:TRENDING (2.5167R, n=15)
- Top blocked: sin datos
### public_safety_policy
- Mejoran: direction:short (10.8004R, n=22), session:NEW_YORK (8.4083R, n=14), trade_location:premium_zone (6.5896R, n=8)
- Empeoran: direction:long (5.225R, n=23), session:LONDON (3.084R, n=14), market_regime:TRENDING (2.5167R, n=15)
- Top allowed: sin datos
- Top blocked: direction:short (-10.8004R, n=22), session:NEW_YORK (-8.4083R, n=14), trade_location:premium_zone (-6.5896R, n=8)
### relaxed_public_safety_v2
- Mejoran: direction:short (10.8004R, n=22), setup_type:SECONDARY_SIGNAL (7.4452R, n=21), session:NEW_YORK (7.4083R, n=13)
- Empeoran: direction:long (4.225R, n=21), session:LONDON (3.084R, n=14), trade_location:near_resistance (2.1323R, n=6)
- Top allowed: session:OVERLAP (2.0R, n=1), market_regime:TRENDING (2.0R, n=1), trade_location:mid_range (2.0R, n=1)
- Top blocked: direction:short (-10.8004R, n=22), setup_type:SECONDARY_SIGNAL (-7.4452R, n=21), session:NEW_YORK (-7.4083R, n=13)
### public_short_canary
- Mejoran: direction:short (10.8004R, n=22), session:NEW_YORK (8.4083R, n=14), trade_location:premium_zone (6.5896R, n=8)
- Empeoran: direction:long (5.225R, n=23), session:LONDON (3.084R, n=14), market_regime:TRENDING (2.5167R, n=15)
- Top allowed: sin datos
- Top blocked: direction:short (-10.8004R, n=22), session:NEW_YORK (-8.4083R, n=14), trade_location:premium_zone (-6.5896R, n=8)
### protection_engine_shadow
- Mejoran: direction:short (9.4775R, n=10), session:NEW_YORK (8.4083R, n=14), trade_location:premium_zone (6.5896R, n=8)
- Empeoran: session:LONDON (3.0225R, n=4), direction:long (1.313R, n=14), trade_location:discount_zone (0.5225R, n=2)
- Top allowed: direction:long (3.912R, n=9), market_regime:TRENDING (3.8022R, n=8), entry_context:BREAKOUT (2.9813R, n=14)
- Top blocked: direction:short (-9.4775R, n=10), session:NEW_YORK (-8.4083R, n=14), trade_location:premium_zone (-6.5896R, n=8)
### pair_universe_filter_shadow
- Mejoran: setup_type:SECONDARY_SIGNAL (4.4775R, n=5), entry_context:BREAKOUT (3.4775R, n=6), direction:long (3.0R, n=5)
- Empeoran: setup_type:MAIN_SIGNAL (1.0R, n=1), session:LONDON (0.5225R, n=2), trade_location:discount_zone (0.5225R, n=2)
- Top allowed: direction:long (8.225R, n=18), trade_location:near_resistance (3.1323R, n=5), session:OVERLAP (2.7489R, n=14)
- Top blocked: setup_type:SECONDARY_SIGNAL (-4.4775R, n=5), entry_context:BREAKOUT (-3.4775R, n=6), session:OVERLAP (-3.0R, n=3)
### kill_switch_risk_guard
- Mejoran: direction:short (9.8004R, n=21), session:NEW_YORK (8.4083R, n=14), trade_location:premium_zone (6.5896R, n=8)
- Empeoran: session:LONDON (5.084R, n=12), direction:long (1.313R, n=19), trade_location:near_resistance (1.1323R, n=7)
- Top allowed: market_regime:TRENDING (5.912R, n=2), session:OVERLAP (4.912R, n=3), direction:long (3.912R, n=4)
- Top blocked: direction:short (-9.8004R, n=21), session:NEW_YORK (-8.4083R, n=14), trade_location:premium_zone (-6.5896R, n=8)
