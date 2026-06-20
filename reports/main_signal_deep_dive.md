# MAIN_SIGNAL_DEEP_DIVE

Generated at: 2026-06-09T16:07:08+00:00
Data path: data
Method: Analyze canonical closed trades where setup_type=MAIN_SIGNAL.
Classification: NOISE

## Executive Summary

- Baseline: trades=40, WR=32.5%, PF=0.8439, TotalR=-3.5754, AvgR=-0.0894
- MAIN_SIGNAL: trades=22, WR=36.3636%, PF=1.0621, TotalR=0.8698, AvgR=0.0395
- SECONDARY_SIGNAL: trades=18, WR=27.7778%, PF=0.5007, TotalR=-4.4452, AvgR=-0.247
- Is MAIN_SIGNAL globally toxic? NO
- Is MAIN_SIGNAL worse than SECONDARY_SIGNAL? NO
- Biggest damage subgroup: market_regime=RANGING (trades=10, PF=0.501, TotalR=-3.4932, class=IMPORTANT)
- Best survivor: direction=long (trades=14, PF=1.7027, TotalR=4.9188, class=NOISE)
- Material PF improvement if removed? NO
- Structural strategy issue evidence: NO
- Recommended action: KEEP

## MAIN_SIGNAL Toxic Subgroups

Criteria: minimum 10 trades, PF < 1, TotalR < 0. Ranked by TotalR then PF.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| market_regime | RANGING | 10 | 3 | 7 | 30.0% | 0.501 | -3.4932 | -0.3493 | IMPORTANT |
| score_bucket | <60 | 14 | 4 | 10 | 28.5714% | 0.6958 | -3.0422 | -0.2173 | IMPORTANT |
| rejection_reason | distance_to_liquidity_penalty | 12 | 3 | 9 | 25.0% | 0.8236 | -1.588 | -0.1323 | IMPORTANT |

## MAIN_SIGNAL Survivors

Criteria: minimum 10 trades, PF > 1.1, TotalR > 0.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| direction | long | 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 | NOISE |
| condition_failed | ["body_ratio_below_threshold" | 12 | 5 | 7 | 41.6667% | 1.2307 | 1.6146 | 0.1346 | NOISE |

## MAIN_SIGNAL vs SECONDARY_SIGNAL Comparison

| Setup | Trades | Wins | Losses | WR | PF | Total R | Avg R | Best Context | Worst Context |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| MAIN_SIGNAL | 22 | 8 | 14 | 36.3636% | 1.0621 | 0.8698 | 0.0395 | direction=long (trades=14, PF=1.7027, TotalR=4.9188, class=NOISE) | market_regime=RANGING (trades=10, PF=0.501, TotalR=-3.4932, class=IMPORTANT) |
| SECONDARY_SIGNAL | 18 | 5 | 13 | 27.7778% | 0.5007 | -4.4452 | -0.247 | none | direction=short (trades=13, PF=0.245, TotalR=-5.7514, class=IMPORTANT) |

## Counterfactual Removal

- PF current: 0.8439
- PF without MAIN_SIGNAL: 0.5007
- TotalR current: -3.5754
- TotalR without MAIN_SIGNAL: -4.4452
- Winrate delta: -4.7222
- Trades removed: 22

## Counterfactual Partial Blocks

| Rule | Removed | PF Before | PF After | TotalR Before | TotalR After | R Improvement | Profitable Lost | Losing Removed | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| MAIN_SIGNAL + directional_confluence_failed | 6 | 0.8439 | 1.0237 | -3.5754 | 0.4246 | 4.0 | 1 | 5 | WATCH |
| MAIN_SIGNAL + choppy_range | 5 | 0.8439 | 0.9696 | -3.5754 | -0.5754 | 3.0 | 1 | 4 | WATCH |
| MAIN_SIGNAL + dirty_sideways_market | 4 | 0.8439 | 0.9208 | -3.5754 | -1.5754 | 2.0 | 1 | 3 | REJECT |
| MAIN_SIGNAL + aligned_bearish | 7 | 0.8439 | 0.9029 | -3.5754 | -1.739 | 1.8364 | 2 | 5 | WATCH |
| MAIN_SIGNAL + distance_to_liquidity_penalty | 12 | 0.8439 | 0.8571 | -3.5754 | -1.9874 | 1.588 | 3 | 9 | SHADOW_TEST |
| MAIN_SIGNAL + score_bucket 80-89 | 1 | 0.8439 | 0.8824 | -3.5754 | -2.5754 | 1.0 | 0 | 1 | REJECT |
| MAIN_SIGNAL + bullish_sweep | 0 | 0.8439 | 0.8439 | -3.5754 | -3.5754 | 0.0 | 0 | 0 | REJECT |
| MAIN_SIGNAL + against_htf | 13 | 0.8439 | 0.7189 | -3.5754 | -4.19 | -0.6146 | 5 | 8 | WATCH |
| MAIN_SIGNAL + near_support | 9 | 0.8439 | 0.7434 | -3.5754 | -4.3374 | -0.762 | 3 | 6 | WATCH |
| MAIN_SIGNAL + HIGH_VOLATILITY | 3 | 0.8439 | 0.702 | -3.5754 | -6.5264 | -2.951 | 2 | 1 | REJECT |
| MAIN_SIGNAL + BREAKOUT | 7 | 0.8439 | 0.5815 | -3.5754 | -8.3306 | -4.7552 | 4 | 3 | WATCH |
| MAIN_SIGNAL + long | 14 | 0.8439 | 0.4659 | -3.5754 | -8.4942 | -4.9188 | 7 | 7 | WATCH |

## Breakdowns

### By Symbol

| By Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SOLUSDT | 4 | 1 | 3 | 25.0% | 0.3333 | -2.0 | -0.5 | WATCH |
| BNBUSDT | 4 | 1 | 3 | 25.0% | 0.5 | -1.5 | -0.375 | WATCH |
| APEUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ETCUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SANDUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| TRXUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| UNIUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| XRPUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ETHUSDT | 2 | 1 | 1 | 50.0% | 1.6568 | 0.6568 | 0.3284 | NOISE |
| DOGEUSDT | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| AVAXUSDT | 1 | 1 | 0 | 100.0% | inf | 1.5068 | 1.5068 | NOISE |
| INJUSDT | 1 | 1 | 0 | 100.0% | inf | 2.951 | 2.951 | NOISE |
| BTCUSDT | 3 | 2 | 1 | 66.6667% | 5.2552 | 4.2552 | 1.4184 | NOISE |

### By Session

| By Session | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| NEW_YORK | 6 | 0 | 6 | 0.0% | 0.0 | -6.0 | -1.0 | WATCH |
| OVERLAP | 8 | 3 | 5 | 37.5% | 1.4838 | 2.4188 | 0.3024 | NOISE |
| LONDON | 8 | 5 | 3 | 62.5% | 2.4837 | 4.451 | 0.5564 | NOISE |

### By Direction

| By Direction | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| short | 8 | 1 | 7 | 12.5% | 0.4216 | -4.049 | -0.5061 | WATCH |
| long | 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 | NOISE |

### By Market Regime

| By Market Regime | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| RANGING | 10 | 3 | 7 | 30.0% | 0.501 | -3.4932 | -0.3493 | IMPORTANT |
| TRENDING | 9 | 3 | 6 | 33.3333% | 1.2353 | 1.412 | 0.1569 | NOISE |
| HIGH_VOLATILITY | 3 | 2 | 1 | 66.6667% | 3.951 | 2.951 | 0.9837 | NOISE |

### By Entry Context

| By Entry Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| CHOPPY_RANGE | 5 | 1 | 4 | 20.0% | 0.25 | -3.0 | -0.6 | WATCH |
| PULLBACK | 7 | 2 | 5 | 28.5714% | 0.8916 | -0.5422 | -0.0775 | WATCH |
| EXHAUSTION | 3 | 1 | 2 | 33.3333% | 0.8284 | -0.3432 | -0.1144 | WATCH |
| BREAKOUT | 7 | 4 | 3 | 57.1429% | 2.5851 | 4.7552 | 0.6793 | NOISE |

### By Liquidity Context

| By Liquidity Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| location:premium_zone | 5 | 0 | 5 | 0.0% | 0.0 | -5.0 | -1.0 | WATCH |
| location:mid_range | 2 | 1 | 1 | 50.0% | 1.6568 | 0.6568 | 0.3284 | NOISE |
| location:near_support | 9 | 3 | 6 | 33.3333% | 1.127 | 0.762 | 0.0847 | NOISE |
| location:discount_zone | 2 | 2 | 0 | 100.0% | inf | 2.0 | 1.0 | NOISE |
| location:near_resistance | 4 | 2 | 2 | 50.0% | 2.2255 | 2.451 | 0.6128 | NOISE |

### By Trade Location

| By Trade Location | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| premium_zone | 5 | 0 | 5 | 0.0% | 0.0 | -5.0 | -1.0 | WATCH |
| mid_range | 2 | 1 | 1 | 50.0% | 1.6568 | 0.6568 | 0.3284 | NOISE |
| near_support | 9 | 3 | 6 | 33.3333% | 1.127 | 0.762 | 0.0847 | NOISE |
| discount_zone | 2 | 2 | 0 | 100.0% | inf | 2.0 | 1.0 | NOISE |
| near_resistance | 4 | 2 | 2 | 50.0% | 2.2255 | 2.451 | 0.6128 | NOISE |

### By Trend Alignment

| By Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_bearish | 7 | 2 | 5 | 28.5714% | 0.6327 | -1.8364 | -0.2623 | WATCH |
| mixed_bullish_vs_bearish | 6 | 2 | 4 | 33.3333% | 0.625 | -1.5 | -0.25 | WATCH |
| aligned_bullish | 7 | 3 | 4 | 42.8571% | 1.2378 | 0.951 | 0.1359 | NOISE |
| mixed_bearish_vs_bullish | 2 | 1 | 1 | 50.0% | 4.2552 | 3.2552 | 1.6276 | NOISE |

### By HTF Alignment

| By HTF Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_with_htf | 9 | 3 | 6 | 33.3333% | 1.0425 | 0.2552 | 0.0284 | NOISE |
| against_htf | 13 | 5 | 8 | 38.4615% | 1.0768 | 0.6146 | 0.0473 | NOISE |

### By Score Bucket

| By Score Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| <60 | 14 | 4 | 10 | 28.5714% | 0.6958 | -3.0422 | -0.2173 | IMPORTANT |
| 80-89 | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| 90+ | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| 70-79 | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| 60-69 | 5 | 3 | 2 | 60.0% | 3.456 | 4.912 | 0.9824 | NOISE |

### By Warning

| By Warning | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| dirty_sideways_market | 4 | 1 | 3 | 25.0% | 0.3333 | -2.0 | -0.5 | WATCH |
| low_volume | 3 | 1 | 2 | 33.3333% | 0.5 | -1.0 | -0.3333 | WATCH |
| none | 7 | 2 | 5 | 28.5714% | 1.051 | 0.2552 | 0.0365 | NOISE |
| against_htf | 13 | 5 | 8 | 38.4615% | 1.0768 | 0.6146 | 0.0473 | NOISE |

### By Penalty

| By Penalty | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 22 | 8 | 14 | 36.3636% | 1.0621 | 0.8698 | 0.0395 | NOISE |

### By Rejection Reason

| By Rejection Reason | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| directional_confluence_failed | 6 | 1 | 5 | 16.6667% | 0.2 | -4.0 | -0.6667 | WATCH |
| distance_to_liquidity_penalty | 12 | 3 | 9 | 25.0% | 0.8236 | -1.588 | -0.1323 | IMPORTANT |
| market_structure_range_penalty | 12 | 5 | 7 | 41.6667% | 1.0654 | 0.4578 | 0.0381 | NOISE |
| body_ratio_below_threshold | 13 | 5 | 8 | 38.4615% | 1.0768 | 0.6146 | 0.0473 | NOISE |
| higher_timeframe_contradicts_long | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| timeframe_alignment_penalty | 8 | 3 | 5 | 37.5% | 1.351 | 1.7552 | 0.2194 | NOISE |
| higher_timeframe_contradicts_short | 2 | 1 | 1 | 50.0% | 4.2552 | 3.2552 | 1.6276 | NOISE |

### By Conditions Failed

| By Conditions Failed | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| "directional_confluence_failed"] | 5 | 1 | 4 | 20.0% | 0.25 | -3.0 | -0.6 | WATCH |
| ["market_structure_range_penalty" | 5 | 1 | 4 | 20.0% | 0.25 | -3.0 | -0.6 | WATCH |
| "timeframe_alignment_penalty" | 5 | 1 | 4 | 20.0% | 0.375 | -2.5 | -0.5 | WATCH |
| ["body_ratio_below_threshold"] | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ["directional_confluence_failed"] | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| "distance_to_liquidity_penalty"] | 6 | 2 | 4 | 33.3333% | 0.7892 | -0.8432 | -0.1405 | WATCH |
| "distance_to_liquidity_penalty" | 6 | 1 | 5 | 16.6667% | 0.851 | -0.7448 | -0.1241 | WATCH |
| "higher_timeframe_contradicts_long"] | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| "market_structure_range_penalty" | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| ["body_ratio_below_threshold" | 12 | 5 | 7 | 41.6667% | 1.2307 | 1.6146 | 0.1346 | NOISE |
| "market_structure_range_penalty"] | 6 | 3 | 3 | 50.0% | 1.8193 | 2.4578 | 0.4096 | NOISE |
| "higher_timeframe_contradicts_short"] | 2 | 1 | 1 | 50.0% | 4.2552 | 3.2552 | 1.6276 | NOISE |
| ["timeframe_alignment_penalty" | 3 | 2 | 1 | 66.6667% | 5.2552 | 4.2552 | 1.4184 | NOISE |

## Recommended Action

KEEP
