# BODY_RATIO_BELOW_THRESHOLD_DEEP_DIVE

Generated at: 2026-06-05T16:55:08+00:00
Data path: data
Method: Exclude bullish_sweep first, then analyze trades with rejection_reason=body_ratio_below_threshold.
Classification: NOISE

## Executive Summary

- Baseline without bullish_sweep: trades=40, WR=32.5%, PF=0.8439, TotalR=-3.5754, AvgR=-0.0894
- body_ratio_below_threshold: trades=16, WR=37.5%, PF=1.0115, TotalR=0.1146, AvgR=0.0072
- Is globally toxic? NO
- Main loss subgroup: htf_alignment=aligned_with_htf (trades=7, PF=0.1667, TotalR=-5.0, class=IMPORTANT)
- Survivor subgroup: htf_alignment=against_htf (trades=9, PF=2.2786, TotalR=5.1146, class=NOISE)
- Future shadow filter evidence: NO
- Material PF improvement if removed? NO

## Toxic Subgroups

Criteria: minimum 5 trades, negative Total R, PF < 1.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| htf_alignment | aligned_with_htf | 7 | 1 | 6 | 14.29% | 0.1667 | -5.0 | -0.7143 | IMPORTANT |
| session | NEW_YORK | 7 | 1 | 6 | 14.29% | 0.25 | -4.5 | -0.6429 | IMPORTANT |
| direction | short | 8 | 1 | 7 | 12.5% | 0.4216 | -4.049 | -0.5061 | IMPORTANT |
| trend_alignment | mixed_bullish_vs_bearish | 7 | 2 | 5 | 28.57% | 0.6 | -2.0 | -0.2857 | IMPORTANT |
| market_regime | RANGING | 6 | 2 | 4 | 33.33% | 0.6267 | -1.4932 | -0.2489 | IMPORTANT |
| market_regime | TRENDING | 9 | 3 | 6 | 33.33% | 0.7761 | -1.3432 | -0.1492 | IMPORTANT |
| trend_alignment | aligned_bearish | 6 | 2 | 4 | 33.33% | 0.7909 | -0.8364 | -0.1394 | IMPORTANT |
| entry_context | PULLBACK | 7 | 2 | 5 | 28.57% | 0.8916 | -0.5422 | -0.0775 | IMPORTANT |

## Survivors

Criteria: minimum 5 trades, PF > 1.1, positive Total R.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| htf_alignment | against_htf | 9 | 5 | 4 | 55.56% | 2.2786 | 5.1146 | 0.5683 | NOISE |
| warning | against_htf | 9 | 5 | 4 | 55.56% | 2.2786 | 5.1146 | 0.5683 | NOISE |
| direction | long | 8 | 5 | 3 | 62.5% | 2.3879 | 4.1636 | 0.5204 | NOISE |
| score_bucket | <60 | 12 | 5 | 7 | 41.67% | 1.2083 | 1.4578 | 0.1215 | NOISE |

## Counterfactual Removal

- PF current: 0.8439
- PF without body_ratio_below_threshold: 0.714
- TotalR current: -3.5754
- TotalR without body_ratio_below_threshold: -3.69
- Winrate delta: -3.33

## Breakdowns

### By Symbol

| By Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SOLUSDT | 2 | 0 | 2 | 0.0% | 0.0 | -2.0 | -1.0 | NOISE |
| BNBUSDT | 4 | 1 | 3 | 25.0% | 0.5 | -1.5 | -0.375 | WATCH |
| ATOMUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ETCUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SANDUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SUIUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| UNIUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| DOGEUSDT | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| DOTUSDT | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |
| AVAXUSDT | 1 | 1 | 0 | 100.0% | inf | 1.5068 | 1.5068 | NOISE |
| ETHUSDT | 1 | 1 | 0 | 100.0% | inf | 1.6568 | 1.6568 | NOISE |
| INJUSDT | 1 | 1 | 0 | 100.0% | inf | 2.951 | 2.951 | NOISE |

### By Session

| By Session | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| NEW_YORK | 7 | 1 | 6 | 14.29% | 0.25 | -4.5 | -0.6429 | IMPORTANT |
| OVERLAP | 5 | 2 | 3 | 40.0% | 1.0545 | 0.1636 | 0.0327 | NOISE |
| LONDON | 4 | 3 | 1 | 75.0% | 5.451 | 4.451 | 1.1128 | NOISE |

### By Direction

| By Direction | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| short | 8 | 1 | 7 | 12.5% | 0.4216 | -4.049 | -0.5061 | IMPORTANT |
| long | 8 | 5 | 3 | 62.5% | 2.3879 | 4.1636 | 0.5204 | NOISE |

### By Market Regime

| By Market Regime | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| RANGING | 6 | 2 | 4 | 33.33% | 0.6267 | -1.4932 | -0.2489 | IMPORTANT |
| TRENDING | 9 | 3 | 6 | 33.33% | 0.7761 | -1.3432 | -0.1492 | IMPORTANT |
| HIGH_VOLATILITY | 1 | 1 | 0 | 100.0% | inf | 2.951 | 2.951 | NOISE |

### By Setup Type

| By Setup Type | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SECONDARY_SIGNAL | 3 | 1 | 2 | 33.33% | 0.75 | -0.5 | -0.1667 | WATCH |
| MAIN_SIGNAL | 13 | 5 | 8 | 38.46% | 1.0768 | 0.6146 | 0.0473 | NOISE |

### By Entry Context

| By Entry Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| CHOPPY_RANGE | 4 | 1 | 3 | 25.0% | 0.3333 | -2.0 | -0.5 | WATCH |
| PULLBACK | 7 | 2 | 5 | 28.57% | 0.8916 | -0.5422 | -0.0775 | IMPORTANT |
| EXHAUSTION | 2 | 1 | 1 | 50.0% | 1.6568 | 0.6568 | 0.3284 | NOISE |
| BREAKOUT | 3 | 2 | 1 | 66.67% | 3.0 | 2.0 | 0.6667 | NOISE |

### By Liquidity Context

| By Liquidity Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| location:premium_zone | 4 | 0 | 4 | 0.0% | 0.0 | -4.0 | -1.0 | WATCH |
| location:mid_range | 5 | 2 | 3 | 40.0% | 1.0523 | 0.1568 | 0.0314 | NOISE |
| location:near_support | 4 | 2 | 2 | 50.0% | 1.2534 | 0.5068 | 0.1267 | NOISE |
| location:near_resistance | 3 | 2 | 1 | 66.67% | 4.451 | 3.451 | 1.1503 | NOISE |

### By Trend Alignment

| By Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| mixed_bullish_vs_bearish | 7 | 2 | 5 | 28.57% | 0.6 | -2.0 | -0.2857 | IMPORTANT |
| aligned_bearish | 6 | 2 | 4 | 33.33% | 0.7909 | -0.8364 | -0.1394 | IMPORTANT |
| aligned_bullish | 3 | 2 | 1 | 66.67% | 3.951 | 2.951 | 0.9837 | NOISE |

### By HTF Alignment

| By HTF Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_with_htf | 7 | 1 | 6 | 14.29% | 0.1667 | -5.0 | -0.7143 | IMPORTANT |
| against_htf | 9 | 5 | 4 | 55.56% | 2.2786 | 5.1146 | 0.5683 | NOISE |

### By Score Bucket

| By Score Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 80-89 | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| 60-69 | 3 | 1 | 2 | 33.33% | 0.8284 | -0.3432 | -0.1144 | WATCH |
| <60 | 12 | 5 | 7 | 41.67% | 1.2083 | 1.4578 | 0.1215 | NOISE |

### By Warning

| By Warning | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 4 | 0 | 4 | 0.0% | 0.0 | -4.0 | -1.0 | WATCH |
| dirty_sideways_market | 4 | 1 | 3 | 25.0% | 0.3333 | -2.0 | -0.5 | WATCH |
| low_volume | 2 | 1 | 1 | 50.0% | 1.0 | 0.0 | 0.0 | NOISE |
| against_htf | 9 | 5 | 4 | 55.56% | 2.2786 | 5.1146 | 0.5683 | NOISE |

### By Penalty

| By Penalty | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 16 | 6 | 10 | 37.5% | 1.0115 | 0.1146 | 0.0072 | NOISE |

## Recommended Action

KEEP
