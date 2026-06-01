# Backtest Runner Summary

- Generated at: 2026-05-29T15:17:24+00:00
- Mode: shadow
- Trades loaded: 40

| Layer | Evaluated | Accepted | Rejected | Total R | WR | Avg R | PF | Max DD | Delta R | Delta vs Current | Confidence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| raw_strategy | 40 | 40 | 0 | -3.5754 | 32.5% | -0.0894 | 0.8439 | -8.9684 | 0.0 | -3.5754 | HIGH |
| public_safety_policy | 40 | 0 | 40 | 0 | 0.0% | 0.0 | 0.0 | 0.0 | 3.5754 | 0.0 | LOW |
| relaxed_public_safety_v2 | 40 | 14 | 26 | 7.3887 | 57.14% | 0.5278 | 2.6548 | -1.1795 | 10.9641 | 7.3887 | MEDIUM |
| public_short_canary | 40 | 0 | 40 | 0 | 0.0% | 0.0 | 0.0 | 0.0 | 3.5754 | 0.0 | LOW |
| protection_engine_shadow | 40 | 18 | 22 | 2.5891 | 33.33% | 0.1438 | 1.2833 | -3.0 | 6.1645 | 2.5891 | MEDIUM |
| pair_universe_filter_shadow | 40 | 37 | 3 | -2.5754 | 32.43% | -0.0696 | 0.8768 | -8.5 | 1.0 | -2.5754 | HIGH |
| kill_switch_risk_guard | 40 | 2 | 38 | -2.0 | 0.0% | -1.0 | 0.0 | -2.0 | 1.5754 | -2.0 | LOW |

## Contexts que más mejoran/empeoran

### raw_strategy
- Mejoran: sin datos
- Empeoran: sin datos
- Top allowed: direction:long (6.225R, n=19), trade_location:near_resistance (3.1323R, n=5), session:LONDON (3.084R, n=14)
- Top blocked: sin datos
### public_safety_policy
- Mejoran: direction:short (9.8004R, n=21), session:NEW_YORK (6.4083R, n=12), trade_location:premium_zone (5.5896R, n=7)
- Empeoran: direction:long (6.225R, n=19), trade_location:near_resistance (3.1323R, n=5), session:LONDON (3.084R, n=14)
- Top allowed: sin datos
- Top blocked: direction:short (-9.8004R, n=21), session:NEW_YORK (-6.4083R, n=12), trade_location:premium_zone (-5.5896R, n=7)
### relaxed_public_safety_v2
- Mejoran: session:NEW_YORK (9.0R, n=9), direction:short (8.6209R, n=19), market_regime:RANGING (6.6108R, n=11)
- Empeoran: trade_location:near_resistance (1.951R, n=2), session:LONDON (0.7635R, n=9), market_regime:HIGH_VOLATILITY (0.0997R, n=7)
- Top allowed: direction:long (8.5682R, n=12), entry_context:BREAKOUT (6.4715R, n=9), setup_type:MAIN_SIGNAL (5.262R, n=9)
- Top blocked: session:NEW_YORK (-9.0R, n=9), direction:short (-8.6209R, n=19), market_regime:RANGING (-6.6108R, n=11)
### public_short_canary
- Mejoran: direction:short (9.8004R, n=21), session:NEW_YORK (6.4083R, n=12), trade_location:premium_zone (5.5896R, n=7)
- Empeoran: direction:long (6.225R, n=19), trade_location:near_resistance (3.1323R, n=5), session:LONDON (3.084R, n=14)
- Top allowed: sin datos
- Top blocked: direction:short (-9.8004R, n=21), session:NEW_YORK (-6.4083R, n=12), trade_location:premium_zone (-5.5896R, n=7)
### protection_engine_shadow
- Mejoran: direction:short (9.4775R, n=10), session:NEW_YORK (6.4083R, n=12), trade_location:premium_zone (5.5896R, n=7)
- Empeoran: direction:long (3.313R, n=12), trade_location:near_resistance (2.1813R, n=2), session:LONDON (2.0225R, n=5)
- Top allowed: setup_type:MAIN_SIGNAL (3.863R, n=10), entry_context:BREAKOUT (2.9813R, n=11), direction:long (2.912R, n=7)
- Top blocked: direction:short (-9.4775R, n=10), session:NEW_YORK (-6.4083R, n=12), trade_location:premium_zone (-5.5896R, n=7)
### pair_universe_filter_shadow
- Mejoran: session:OVERLAP (2.0R, n=2), direction:long (1.0R, n=3), market_regime:RANGING (1.0R, n=1)
- Empeoran: session:LONDON (1.0R, n=1), trade_location:discount_zone (1.0R, n=1)
- Top allowed: direction:long (7.225R, n=16), trade_location:near_resistance (3.1323R, n=5), session:LONDON (2.084R, n=13)
- Top blocked: session:OVERLAP (-2.0R, n=2), market_regime:RANGING (-1.0R, n=1), trade_location:near_support (-1.0R, n=1)
### kill_switch_risk_guard
- Mejoran: direction:short (8.8004R, n=20), session:NEW_YORK (6.4083R, n=12), trade_location:premium_zone (5.5896R, n=7)
- Empeoran: direction:long (7.225R, n=18), session:LONDON (5.084R, n=12), trade_location:near_resistance (3.1323R, n=5)
- Top allowed: direction:long (-1.0R, n=1), setup_type:MAIN_SIGNAL (-1.0R, n=1), entry_context:CHOPPY_RANGE (-1.0R, n=1)
- Top blocked: direction:short (-8.8004R, n=20), session:NEW_YORK (-6.4083R, n=12), trade_location:premium_zone (-5.5896R, n=7)
