# NEW_YORK_RANGING_DEEP_DIVE

Generated at: 2026-06-06T16:50:11+00:00
Data path: data
Method: Exclude bullish_sweep and against_htf+BREAKOUT first, then analyze session=NEW_YORK and market_regime=RANGING.
Classification: IMPORTANT

## Executive Summary

- Baseline after active blocks: trades=32, WR=31.25%, PF=0.7713, TotalR=-4.5446, AvgR=-0.142
- NEW_YORK + RANGING: trades=7, WR=28.57%, PF=0.2183, TotalR=-3.9083, AvgR=-0.5583
- Is NEW_YORK + RANGING globally toxic? YES
- Main loss subgroup: direction=short (trades=5, PF=0.0, TotalR=-5.0, class=IMPORTANT)
- Survivor subgroup: none
- Material PF improvement if removed? YES
- Future shadow filter evidence: YES

## Toxic NEW_YORK RANGING Subgroups

Criteria: minimum 3 trades, negative Total R, PF < 1.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| direction | short | 5 | 0 | 5 | 0.0% | 0.0 | -5.0 | -1.0 | IMPORTANT |
| setup_type | MAIN_SIGNAL | 3 | 0 | 3 | 0.0% | 0.0 | -3.0 | -1.0 | IMPORTANT |
| score_bucket | <60 | 3 | 0 | 3 | 0.0% | 0.0 | -3.0 | -1.0 | IMPORTANT |
| rejection_reason | body_ratio_below_threshold | 3 | 0 | 3 | 0.0% | 0.0 | -3.0 | -1.0 | IMPORTANT |
| entry_context | CHOPPY_RANGE | 4 | 1 | 3 | 25.0% | 0.1368 | -2.5896 | -0.6474 | IMPORTANT |
| liquidity_context | location:premium_zone | 4 | 1 | 3 | 25.0% | 0.1368 | -2.5896 | -0.6474 | IMPORTANT |
| warning | dirty_sideways_market | 4 | 1 | 3 | 25.0% | 0.1368 | -2.5896 | -0.6474 | IMPORTANT |
| trend_alignment | aligned_bearish | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | IMPORTANT |
| htf_alignment | against_htf | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | IMPORTANT |
| warning | against_htf | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | IMPORTANT |
| penalty | none | 7 | 2 | 5 | 28.57% | 0.2183 | -3.9083 | -0.5583 | IMPORTANT |
| rejection_reason | market_structure_range_penalty | 7 | 2 | 5 | 28.57% | 0.2183 | -3.9083 | -0.5583 | IMPORTANT |
| htf_alignment | aligned_with_htf | 4 | 1 | 3 | 25.0% | 0.2271 | -2.3187 | -0.5797 | IMPORTANT |
| trend_alignment | aligned_bullish | 3 | 1 | 2 | 33.33% | 0.3407 | -1.3187 | -0.4396 | IMPORTANT |
| score_bucket | 60-69 | 3 | 1 | 2 | 33.33% | 0.3407 | -1.3187 | -0.4396 | IMPORTANT |
| rejection_reason | distance_to_liquidity_penalty | 3 | 1 | 2 | 33.33% | 0.3407 | -1.3187 | -0.4396 | IMPORTANT |
| setup_type | SECONDARY_SIGNAL | 4 | 2 | 2 | 50.0% | 0.5458 | -0.9083 | -0.2271 | IMPORTANT |

## NEW_YORK RANGING Survivors

Criteria: minimum 3 trades, PF > 1.1, positive Total R.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

## Counterfactual Removal

- PF current after active blocks: 0.7713
- PF without NEW_YORK_RANGING: 0.9572
- TotalR current: -4.5446
- TotalR without NEW_YORK_RANGING: -0.6363
- Winrate delta: 0.75
- Trades removed: 7

## Breakdowns

### By Symbol

| By Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| ATOMUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ETCUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ICPUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| UNIUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ETHUSDT | 2 | 1 | 1 | 50.0% | 0.6813 | -0.3187 | -0.1593 | WATCH |
| AVAXUSDT | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |

### By Direction

| By Direction | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| short | 5 | 0 | 5 | 0.0% | 0.0 | -5.0 | -1.0 | IMPORTANT |
| long | 2 | 2 | 0 | 100.0% | inf | 1.0917 | 0.5458 | NOISE |

### By Setup Type

| By Setup Type | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| MAIN_SIGNAL | 3 | 0 | 3 | 0.0% | 0.0 | -3.0 | -1.0 | IMPORTANT |
| SECONDARY_SIGNAL | 4 | 2 | 2 | 50.0% | 0.5458 | -0.9083 | -0.2271 | IMPORTANT |

### By Entry Context

| By Entry Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| CHOPPY_RANGE | 4 | 1 | 3 | 25.0% | 0.1368 | -2.5896 | -0.6474 | IMPORTANT |
| EXHAUSTION | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| BREAKOUT | 2 | 1 | 1 | 50.0% | 0.6813 | -0.3187 | -0.1593 | WATCH |

### By Liquidity Context

| By Liquidity Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| location:premium_zone | 4 | 1 | 3 | 25.0% | 0.1368 | -2.5896 | -0.6474 | IMPORTANT |
| location:mid_range | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| location:near_support | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| location:near_resistance | 1 | 1 | 0 | 100.0% | inf | 0.6813 | 0.6813 | NOISE |

### By Trend Alignment

| By Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_bearish | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | IMPORTANT |
| aligned_bullish | 3 | 1 | 2 | 33.33% | 0.3407 | -1.3187 | -0.4396 | IMPORTANT |
| mixed_bullish_vs_bearish | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By HTF Alignment

| By HTF Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_with_htf | 4 | 1 | 3 | 25.0% | 0.2271 | -2.3187 | -0.5797 | IMPORTANT |
| against_htf | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | IMPORTANT |

### By Score Bucket

| By Score Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| <60 | 3 | 0 | 3 | 0.0% | 0.0 | -3.0 | -1.0 | IMPORTANT |
| 60-69 | 3 | 1 | 2 | 33.33% | 0.3407 | -1.3187 | -0.4396 | IMPORTANT |
| 80-89 | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |

### By Warning

| By Warning | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| dirty_sideways_market | 4 | 1 | 3 | 25.0% | 0.1368 | -2.5896 | -0.6474 | IMPORTANT |
| against_htf | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | IMPORTANT |
| low_volume | 2 | 1 | 1 | 50.0% | 0.4104 | -0.5896 | -0.2948 | WATCH |
| none | 2 | 1 | 1 | 50.0% | 0.6813 | -0.3187 | -0.1593 | WATCH |

### By Penalty

| By Penalty | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 7 | 2 | 5 | 28.57% | 0.2183 | -3.9083 | -0.5583 | IMPORTANT |

### By Rejection Reason

| By Rejection Reason | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| market_structure_range_penalty | 7 | 2 | 5 | 28.57% | 0.2183 | -3.9083 | -0.5583 | IMPORTANT |
| body_ratio_below_threshold | 3 | 0 | 3 | 0.0% | 0.0 | -3.0 | -1.0 | IMPORTANT |
| distance_to_liquidity_penalty | 3 | 1 | 2 | 33.33% | 0.3407 | -1.3187 | -0.4396 | IMPORTANT |
| timeframe_alignment_penalty | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| directional_confluence_failed | 2 | 1 | 1 | 50.0% | 0.4104 | -0.5896 | -0.2948 | WATCH |
| secondary_setup_requirements_failed | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |

## Recommended Action

SHADOW_BLOCK
