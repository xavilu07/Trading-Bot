# MAIN_SIGNAL_LONG_DNA

Generated at: 2026-06-09T16:35:14+00:00
Data path: data
Method: Analyze canonical closed trades where setup_type=MAIN_SIGNAL and direction=long.
Classification: NOISE

## Executive Summary

- Baseline: trades=40, WR=32.5%, PF=0.8439, TotalR=-3.5754, AvgR=-0.0894
- MAIN_SIGNAL LONG: trades=14, WR=50.0%, PF=1.7027, TotalR=4.9188, AvgR=0.3513
- MAIN_SIGNAL SHORT: trades=8, WR=12.5%, PF=0.4216, TotalR=-4.049, AvgR=-0.5061
- What causes MAIN_SIGNAL LONG losses? No toxic MAIN_SIGNAL LONG cluster met minimum sample criteria.
- Most damaging subgroup: none
- Best survivor: penalty=none (trades=14, PF=1.7027, TotalR=4.9188, class=NOISE)
- Is MAIN_SIGNAL LONG salvageable? YES
- Partial blocking beats full removal? YES
- Dominant issue: unknown
- Recommended action: KEEP

## Toxic LONG Clusters

Criteria: minimum 10 trades, PF < 1, TotalR < 0.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

## Profitable LONG Survivors

Criteria: minimum 10 trades, PF > 1.1, TotalR > 0.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| penalty | none | 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 | NOISE |

## LONG vs SHORT DNA Comparison

| Side | Trades | Wins | Losses | WR | PF | Total R | Avg R | Top Symbol | Top Session | Top Regime | Top Liquidity | Top HTF |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|
| MAIN_SIGNAL_LONG | 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 | BNBUSDT (21.4286%) | OVERLAP (57.1429%) | RANGING (42.8571%) | location:near_support (64.2857%) | against_htf (64.2857%) |
| MAIN_SIGNAL_SHORT | 8 | 1 | 7 | 12.5% | 0.4216 | -4.049 | -0.5061 | BNBUSDT (12.5%) | NEW_YORK (62.5%) | RANGING (50.0%) | location:premium_zone (62.5%) | against_htf (50.0%) |

## Counterfactual Removal

- PF current: 0.8439
- PF without MAIN_SIGNAL_LONG: 0.4659
- TotalR current: -3.5754
- TotalR without MAIN_SIGNAL_LONG: -8.4942
- Winrate delta: -9.4231
- Trades removed: 14

## Counterfactual Partial Blocks

| Rule | Removed | PF Before | PF After | TotalR Before | TotalR After | R Improvement | Profitable Lost | Losing Removed | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| MAIN_SIGNAL LONG + directional_confluence_failed | 4 | 0.8439 | 0.9208 | -3.5754 | -1.5754 | 2.0 | 1 | 3 | REJECT |
| MAIN_SIGNAL LONG + bullish_sweep | 0 | 0.8439 | 0.8439 | -3.5754 | -3.5754 | 0.0 | 0 | 0 | REJECT |
| MAIN_SIGNAL LONG + HIGH_VOLATILITY | 2 | 0.8439 | 0.8368 | -3.5754 | -3.5754 | 0.0 | 1 | 1 | REJECT |
| MAIN_SIGNAL LONG + RANGING | 6 | 0.8439 | 0.7949 | -3.5754 | -4.0822 | -0.5068 | 3 | 3 | WATCH |
| MAIN_SIGNAL LONG + against_htf | 9 | 0.8439 | 0.7632 | -3.5754 | -4.239 | -0.6636 | 4 | 5 | WATCH |
| MAIN_SIGNAL LONG + near_support | 9 | 0.8439 | 0.7434 | -3.5754 | -4.3374 | -0.762 | 3 | 6 | WATCH |
| MAIN_SIGNAL LONG + body_ratio_below_threshold | 7 | 0.8439 | 0.6865 | -3.5754 | -6.239 | -2.6636 | 4 | 3 | WATCH |
| MAIN_SIGNAL LONG + distance_to_liquidity_penalty | 7 | 0.8439 | 0.6304 | -3.5754 | -6.9874 | -3.412 | 3 | 4 | WATCH |
| MAIN_SIGNAL LONG + BREAKOUT | 7 | 0.8439 | 0.5815 | -3.5754 | -8.3306 | -4.7552 | 4 | 3 | WATCH |

## Breakdowns

### By Symbol

| By Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| APEUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| XRPUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SOLUSDT | 3 | 1 | 2 | 33.3333% | 0.5 | -1.0 | -0.3333 | WATCH |
| BNBUSDT | 3 | 1 | 2 | 33.3333% | 0.75 | -0.5 | -0.1667 | WATCH |
| DOGEUSDT | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| AVAXUSDT | 1 | 1 | 0 | 100.0% | inf | 1.5068 | 1.5068 | NOISE |
| ETHUSDT | 1 | 1 | 0 | 100.0% | inf | 1.6568 | 1.6568 | NOISE |
| BTCUSDT | 3 | 2 | 1 | 66.6667% | 5.2552 | 4.2552 | 1.4184 | NOISE |

### By Session

| By Session | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| NEW_YORK | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| OVERLAP | 8 | 3 | 5 | 37.5% | 1.4838 | 2.4188 | 0.3024 | NOISE |
| LONDON | 5 | 4 | 1 | 80.0% | 4.5 | 3.5 | 0.7 | NOISE |

### By Market Regime

| By Market Regime | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| HIGH_VOLATILITY | 2 | 1 | 1 | 50.0% | 1.0 | 0.0 | 0.0 | NOISE |
| RANGING | 6 | 3 | 3 | 50.0% | 1.1689 | 0.5068 | 0.0845 | NOISE |
| TRENDING | 6 | 3 | 3 | 50.0% | 2.4707 | 4.412 | 0.7353 | NOISE |

### By Entry Context

| By Entry Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| PULLBACK | 3 | 1 | 2 | 33.3333% | 0.7534 | -0.4932 | -0.1644 | WATCH |
| CHOPPY_RANGE | 2 | 1 | 1 | 50.0% | 1.0 | 0.0 | 0.0 | NOISE |
| EXHAUSTION | 2 | 1 | 1 | 50.0% | 1.6568 | 0.6568 | 0.3284 | NOISE |
| BREAKOUT | 7 | 4 | 3 | 57.1429% | 2.5851 | 4.7552 | 0.6793 | NOISE |

### By Liquidity Context

| By Liquidity Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| location:mid_range | 2 | 1 | 1 | 50.0% | 1.6568 | 0.6568 | 0.3284 | NOISE |
| location:near_support | 9 | 3 | 6 | 33.3333% | 1.127 | 0.762 | 0.0847 | NOISE |
| location:near_resistance | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |
| location:discount_zone | 2 | 2 | 0 | 100.0% | inf | 2.0 | 1.0 | NOISE |

### By Trade Location

| By Trade Location | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| mid_range | 2 | 1 | 1 | 50.0% | 1.6568 | 0.6568 | 0.3284 | NOISE |
| near_support | 9 | 3 | 6 | 33.3333% | 1.127 | 0.762 | 0.0847 | NOISE |
| near_resistance | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |
| discount_zone | 2 | 2 | 0 | 100.0% | inf | 2.0 | 1.0 | NOISE |

### By Trend Alignment

| By Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_bearish | 7 | 2 | 5 | 28.5714% | 0.6327 | -1.8364 | -0.2623 | WATCH |
| aligned_bullish | 3 | 2 | 1 | 66.6667% | 2.0 | 1.0 | 0.3333 | NOISE |
| mixed_bullish_vs_bearish | 2 | 2 | 0 | 100.0% | inf | 2.5 | 1.25 | NOISE |
| mixed_bearish_vs_bullish | 2 | 1 | 1 | 50.0% | 4.2552 | 3.2552 | 1.6276 | NOISE |

### By HTF Alignment

| By HTF Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| against_htf | 9 | 4 | 5 | 44.4444% | 1.1327 | 0.6636 | 0.0737 | NOISE |
| aligned_with_htf | 5 | 3 | 2 | 60.0% | 3.1276 | 4.2552 | 0.851 | NOISE |

### By Score Bucket

| By Score Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 80-89 | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| 90+ | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| 70-79 | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| <60 | 6 | 3 | 3 | 50.0% | 1.3356 | 1.0068 | 0.1678 | NOISE |
| 60-69 | 5 | 3 | 2 | 60.0% | 3.456 | 4.912 | 0.9824 | NOISE |

### By Warning

| By Warning | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| dirty_sideways_market | 2 | 1 | 1 | 50.0% | 1.0 | 0.0 | 0.0 | NOISE |
| low_volume | 2 | 1 | 1 | 50.0% | 1.0 | 0.0 | 0.0 | NOISE |
| against_htf | 9 | 4 | 5 | 44.4444% | 1.1327 | 0.6636 | 0.0737 | NOISE |
| none | 4 | 2 | 2 | 50.0% | 2.6276 | 3.2552 | 0.8138 | NOISE |

### By Penalty

| By Penalty | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 | NOISE |

### By Rejection Reason

| By Rejection Reason | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| directional_confluence_failed | 4 | 1 | 3 | 25.0% | 0.3333 | -2.0 | -0.5 | WATCH |
| higher_timeframe_contradicts_long | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| market_structure_range_penalty | 7 | 4 | 3 | 57.1429% | 1.5023 | 1.5068 | 0.2153 | NOISE |
| body_ratio_below_threshold | 7 | 4 | 3 | 57.1429% | 1.8879 | 2.6636 | 0.3805 | NOISE |
| higher_timeframe_contradicts_short | 2 | 1 | 1 | 50.0% | 4.2552 | 3.2552 | 1.6276 | NOISE |
| distance_to_liquidity_penalty | 7 | 3 | 4 | 42.8571% | 1.853 | 3.412 | 0.4874 | NOISE |
| timeframe_alignment_penalty | 4 | 3 | 1 | 75.0% | 6.7552 | 5.7552 | 1.4388 | NOISE |

### By Conditions Failed

| By Conditions Failed | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| ["body_ratio_below_threshold"] | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ["directional_confluence_failed"] | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| "directional_confluence_failed"] | 3 | 1 | 2 | 33.3333% | 0.5 | -1.0 | -0.3333 | WATCH |
| ["market_structure_range_penalty" | 3 | 1 | 2 | 33.3333% | 0.5 | -1.0 | -0.3333 | WATCH |
| "higher_timeframe_contradicts_long"] | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| "market_structure_range_penalty" | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| "distance_to_liquidity_penalty" | 4 | 1 | 3 | 25.0% | 1.4184 | 1.2552 | 0.3138 | NOISE |
| "timeframe_alignment_penalty" | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |
| "market_structure_range_penalty"] | 3 | 2 | 1 | 66.6667% | 2.5068 | 1.5068 | 0.5023 | NOISE |
| "distance_to_liquidity_penalty"] | 3 | 2 | 1 | 66.6667% | 3.1568 | 2.1568 | 0.7189 | NOISE |
| "higher_timeframe_contradicts_short"] | 2 | 1 | 1 | 50.0% | 4.2552 | 3.2552 | 1.6276 | NOISE |
| ["body_ratio_below_threshold" | 6 | 4 | 2 | 66.6667% | 2.8318 | 3.6636 | 0.6106 | NOISE |
| ["timeframe_alignment_penalty" | 3 | 2 | 1 | 66.6667% | 5.2552 | 4.2552 | 1.4184 | NOISE |

## Recommended Action

KEEP
