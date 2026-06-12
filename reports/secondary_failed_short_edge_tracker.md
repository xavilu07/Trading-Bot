# SECONDARY_FAILED_SHORT_EDGE_TRACKER

Generated at: 2026-06-12T15:10:06+00:00
Data path: data
Trades file: data/paper_trading/trades.csv
Mode: offline/shadow only
Target reason: secondary_setup_requirements_failed
Recommendation summary: INSUFFICIENT_DATA

## Profile Summary

| Profile | Description | Trades | Closed | Wins | Losses | WR | Gross Win R | Gross Loss R | PF | Total R | Avg R | Recommendation |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| BASE | secondary_setup_requirements_failed + short | 7 | 6 | 1 | 5 | 16.6667% | 1.5 | 2.5083 | 0.598 | -1.0083 | -0.1681 | INSUFFICIENT_DATA |
| PROFILE_A | BASE + trade_location == mid_range | 2 | 2 | 0 | 2 | 0.0% | 0.0 | 1.21 | 0.0 | -1.21 | -0.605 | INSUFFICIENT_DATA |
| PROFILE_B | BASE + session == LONDON + market_regime == RANGING | 2 | 2 | 1 | 1 | 50.0% | 1.5 | 0.4775 | 3.1414 | 1.0225 | 0.5112 | INSUFFICIENT_DATA |
| PROFILE_C | BASE + session == ASIA + trade_location == mid_range | 0 | 0 | 0 | 0 | 0.0% | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | INSUFFICIENT_DATA |
| PROFILE_D | BASE + market_regime == HIGH_VOLATILITY + trade_location == mid_range | 2 | 2 | 0 | 2 | 0.0% | 0.0 | 1.21 | 0.0 | -1.21 | -0.605 | INSUFFICIENT_DATA |

## Profile Rules

### BASE

- Description: secondary_setup_requirements_failed + short
- Rules: {"contains": "secondary_setup_requirements_failed", "direction": "short"}
- Recommendation: INSUFFICIENT_DATA

### PROFILE_A

- Description: BASE + trade_location == mid_range
- Rules: {"trade_location": "mid_range"}
- Recommendation: INSUFFICIENT_DATA

### PROFILE_B

- Description: BASE + session == LONDON + market_regime == RANGING
- Rules: {"market_regime": "RANGING", "session": "LONDON"}
- Recommendation: INSUFFICIENT_DATA

### PROFILE_C

- Description: BASE + session == ASIA + trade_location == mid_range
- Rules: {"session": "ASIA", "trade_location": "mid_range"}
- Recommendation: INSUFFICIENT_DATA

### PROFILE_D

- Description: BASE + market_regime == HIGH_VOLATILITY + trade_location == mid_range
- Rules: {"market_regime": "HIGH_VOLATILITY", "trade_location": "mid_range"}
- Recommendation: INSUFFICIENT_DATA
