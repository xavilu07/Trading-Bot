# NEW_YORK_DEEP_DIVE

Generated at: 2026-06-06T16:39:53+00:00
Data path: data
Method: Exclude bullish_sweep and against_htf+BREAKOUT first, then analyze session=NEW_YORK.
Classification: CRITICAL

## Executive Summary

- Baseline after active blocks: trades=32, WR=31.25%, PF=0.7713, TotalR=-4.5446, AvgR=-0.142
- NEW_YORK: trades=11, WR=18.18%, PF=0.1213, TotalR=-7.9083, AvgR=-0.7189
- Is NEW_YORK globally toxic? YES
- Main loss subgroup: direction=short (trades=8, PF=0.0, TotalR=-8.0, class=IMPORTANT)
- Survivor subgroup: none
- Material PF improvement if removed? YES
- Future shadow filter evidence: YES

## Toxic NEW_YORK Subgroups

Criteria: minimum 5 trades, negative Total R, PF < 1.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| direction | short | 8 | 0 | 8 | 0.0% | 0.0 | -8.0 | -1.0 | IMPORTANT |
| setup_type | MAIN_SIGNAL | 6 | 0 | 6 | 0.0% | 0.0 | -6.0 | -1.0 | IMPORTANT |
| score_bucket | <60 | 6 | 0 | 6 | 0.0% | 0.0 | -6.0 | -1.0 | IMPORTANT |
| rejection_reason | body_ratio_below_threshold | 6 | 0 | 6 | 0.0% | 0.0 | -6.0 | -1.0 | IMPORTANT |
| liquidity_context | location:premium_zone | 6 | 1 | 5 | 16.67% | 0.0821 | -4.5896 | -0.7649 | IMPORTANT |
| htf_alignment | aligned_with_htf | 8 | 1 | 7 | 12.5% | 0.0973 | -6.3187 | -0.7898 | IMPORTANT |
| penalty | none | 11 | 2 | 9 | 18.18% | 0.1213 | -7.9083 | -0.7189 | CRITICAL |
| warning | none | 6 | 1 | 5 | 16.67% | 0.1363 | -4.3187 | -0.7198 | IMPORTANT |
| rejection_reason | distance_to_liquidity_penalty | 5 | 1 | 4 | 20.0% | 0.1703 | -3.3187 | -0.6637 | IMPORTANT |
| market_regime | RANGING | 7 | 2 | 5 | 28.57% | 0.2183 | -3.9083 | -0.5583 | IMPORTANT |
| rejection_reason | market_structure_range_penalty | 7 | 2 | 5 | 28.57% | 0.2183 | -3.9083 | -0.5583 | IMPORTANT |
| setup_type | SECONDARY_SIGNAL | 5 | 2 | 3 | 40.0% | 0.3639 | -1.9083 | -0.3817 | IMPORTANT |

## NEW_YORK Survivors

Criteria: minimum 5 trades, PF > 1.1, positive Total R.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

## Counterfactual Removal

- PF current: 0.7713
- PF without NEW_YORK: 1.3094
- TotalR current: -4.5446
- TotalR without NEW_YORK: 3.3637
- Winrate delta: 6.85
- Trades removed: 11

## Breakdowns

### By Symbol

| By Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| APEUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ATOMUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ETCUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ICPUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SANDUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SOLUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SUIUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| UNIUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ETHUSDT | 2 | 1 | 1 | 50.0% | 0.6813 | -0.3187 | -0.1593 | NOISE |
| AVAXUSDT | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |

### By Direction

| By Direction | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| short | 8 | 0 | 8 | 0.0% | 0.0 | -8.0 | -1.0 | IMPORTANT |
| long | 3 | 2 | 1 | 66.67% | 1.0917 | 0.0917 | 0.0306 | NOISE |

### By Market Regime

| By Market Regime | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| RANGING | 7 | 2 | 5 | 28.57% | 0.2183 | -3.9083 | -0.5583 | IMPORTANT |
| TRENDING | 3 | 0 | 3 | 0.0% | 0.0 | -3.0 | -1.0 | WATCH |
| HIGH_VOLATILITY | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By Setup Type

| By Setup Type | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| MAIN_SIGNAL | 6 | 0 | 6 | 0.0% | 0.0 | -6.0 | -1.0 | IMPORTANT |
| SECONDARY_SIGNAL | 5 | 2 | 3 | 40.0% | 0.3639 | -1.9083 | -0.3817 | IMPORTANT |

### By Entry Context

| By Entry Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| CHOPPY_RANGE | 4 | 1 | 3 | 25.0% | 0.1368 | -2.5896 | -0.6474 | WATCH |
| BREAKOUT | 4 | 1 | 3 | 25.0% | 0.2271 | -2.3187 | -0.5797 | WATCH |
| PULLBACK | 2 | 0 | 2 | 0.0% | 0.0 | -2.0 | -1.0 | NOISE |
| EXHAUSTION | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By Liquidity Context

| By Liquidity Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| location:premium_zone | 6 | 1 | 5 | 16.67% | 0.0821 | -4.5896 | -0.7649 | IMPORTANT |
| location:mid_range | 2 | 0 | 2 | 0.0% | 0.0 | -2.0 | -1.0 | NOISE |
| location:near_support | 2 | 0 | 2 | 0.0% | 0.0 | -2.0 | -1.0 | NOISE |
| location:near_resistance | 1 | 1 | 0 | 100.0% | inf | 0.6813 | 0.6813 | NOISE |

### By Trend Alignment

| By Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| mixed_bullish_vs_bearish | 4 | 0 | 4 | 0.0% | 0.0 | -4.0 | -1.0 | WATCH |
| aligned_bullish | 4 | 1 | 3 | 25.0% | 0.2271 | -2.3187 | -0.5797 | WATCH |
| aligned_bearish | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | WATCH |

### By HTF Alignment

| By HTF Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_with_htf | 8 | 1 | 7 | 12.5% | 0.0973 | -6.3187 | -0.7898 | IMPORTANT |
| against_htf | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | WATCH |

### By Score Bucket

| By Score Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| <60 | 6 | 0 | 6 | 0.0% | 0.0 | -6.0 | -1.0 | IMPORTANT |
| 60-69 | 3 | 1 | 2 | 33.33% | 0.3407 | -1.3187 | -0.4396 | WATCH |
| 90+ | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| 80-89 | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |

### By Warning

| By Warning | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 6 | 1 | 5 | 16.67% | 0.1363 | -4.3187 | -0.7198 | IMPORTANT |
| dirty_sideways_market | 4 | 1 | 3 | 25.0% | 0.1368 | -2.5896 | -0.6474 | WATCH |
| against_htf | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | WATCH |
| low_volume | 2 | 1 | 1 | 50.0% | 0.4104 | -0.5896 | -0.2948 | NOISE |

### By Penalty

| By Penalty | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 11 | 2 | 9 | 18.18% | 0.1213 | -7.9083 | -0.7189 | CRITICAL |

### By Rejection Reason

| By Rejection Reason | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| body_ratio_below_threshold | 6 | 0 | 6 | 0.0% | 0.0 | -6.0 | -1.0 | IMPORTANT |
| timeframe_alignment_penalty | 4 | 0 | 4 | 0.0% | 0.0 | -4.0 | -1.0 | WATCH |
| market_structure_range_penalty | 7 | 2 | 5 | 28.57% | 0.2183 | -3.9083 | -0.5583 | IMPORTANT |
| distance_to_liquidity_penalty | 5 | 1 | 4 | 20.0% | 0.1703 | -3.3187 | -0.6637 | IMPORTANT |
| directional_confluence_failed | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | WATCH |
| secondary_setup_requirements_failed | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |

## Recommended Action

FULL_BLOCK
