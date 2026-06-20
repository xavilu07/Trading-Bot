# AGAINST_HTF_DEEP_DIVE

Generated at: 2026-06-05T17:02:28+00:00
Data path: data
Method: Exclude bullish_sweep first, then analyze trades where warnings contain against_htf or HTF alignment is against_htf.
Classification: NOISE

## Executive Summary

- Baseline without bullish_sweep: trades=40, WR=32.5%, PF=0.8439, TotalR=-3.5754, AvgR=-0.0894
- against_htf: trades=19, WR=36.84%, PF=1.0493, TotalR=0.4942, AvgR=0.026
- Is globally toxic? NO
- Main loss subgroup: market_regime=RANGING (trades=8, PF=0.3195, TotalR=-4.0828, class=IMPORTANT)
- Survivor subgroup: other_warning=none (trades=15, PF=1.4386, TotalR=3.0838, class=NOISE)
- Material PF improvement if removed? NO
- Future shadow filter evidence: NO

## Toxic Subgroups

Criteria: minimum 5 trades, negative Total R, PF < 1.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| market_regime | RANGING | 8 | 2 | 6 | 25.0% | 0.3195 | -4.0828 | -0.5103 | IMPORTANT |
| liquidity_context | location:near_support | 5 | 1 | 4 | 20.0% | 0.3767 | -2.4932 | -0.4986 | IMPORTANT |
| direction | short | 8 | 1 | 7 | 12.5% | 0.5866 | -2.0798 | -0.26 | IMPORTANT |
| trend_alignment | aligned_bullish | 8 | 1 | 7 | 12.5% | 0.5866 | -2.0798 | -0.26 | IMPORTANT |
| session | OVERLAP | 7 | 2 | 5 | 28.57% | 0.6816 | -1.4777 | -0.2111 | IMPORTANT |
| trend_alignment | aligned_bearish | 8 | 3 | 5 | 37.5% | 0.7148 | -1.426 | -0.1783 | IMPORTANT |
| setup_type | SECONDARY_SIGNAL | 6 | 2 | 4 | 33.33% | 0.9407 | -0.1204 | -0.0201 | IMPORTANT |

## Survivors

Criteria: minimum 5 trades, PF > 1.1, positive Total R.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| other_warning | none | 15 | 6 | 9 | 40.0% | 1.4386 | 3.0838 | 0.2056 | NOISE |
| market_regime | TRENDING | 5 | 3 | 2 | 60.0% | 2.3284 | 2.6568 | 0.5314 | NOISE |
| direction | long | 11 | 6 | 5 | 54.55% | 1.5148 | 2.574 | 0.234 | NOISE |
| session | LONDON | 8 | 3 | 5 | 37.5% | 1.6082 | 2.0615 | 0.2577 | NOISE |
| market_regime | HIGH_VOLATILITY | 6 | 2 | 4 | 33.33% | 1.9455 | 1.9202 | 0.32 | NOISE |
| score_bucket | <60 | 10 | 4 | 6 | 40.0% | 1.243 | 1.4578 | 0.1458 | NOISE |
| entry_context | BREAKOUT | 8 | 3 | 5 | 37.5% | 1.3198 | 0.9692 | 0.1212 | NOISE |
| liquidity_context | location:mid_range | 5 | 2 | 3 | 40.0% | 1.4284 | 0.9468 | 0.1894 | NOISE |

## Counterfactual Removal

- PF current: 0.8439
- PF without against_htf: 0.6839
- TotalR current: -3.5754
- TotalR without against_htf: -4.0696
- Winrate delta: -3.93
- Trades removed: 19

## Breakdowns

### By Symbol

| By Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| DOGEUSDT | 3 | 0 | 3 | 0.0% | 0.0 | -1.8513 | -0.6171 | WATCH |
| ETCUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| TRXUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| XRPUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SOLUSDT | 3 | 1 | 2 | 33.33% | 0.5 | -1.0 | -0.3333 | WATCH |
| BNBUSDT | 3 | 1 | 2 | 33.33% | 0.75 | -0.5 | -0.1667 | WATCH |
| ETHUSDT | 3 | 1 | 2 | 33.33% | 1.4047 | 0.4773 | 0.1591 | NOISE |
| DOTUSDT | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |
| AVAXUSDT | 2 | 2 | 0 | 100.0% | inf | 1.9172 | 0.9586 | NOISE |
| INJUSDT | 1 | 1 | 0 | 100.0% | inf | 2.951 | 2.951 | NOISE |

### By Session

| By Session | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| OVERLAP | 7 | 2 | 5 | 28.57% | 0.6816 | -1.4777 | -0.2111 | IMPORTANT |
| NEW_YORK | 4 | 2 | 2 | 50.0% | 0.9552 | -0.0896 | -0.0224 | WATCH |
| LONDON | 8 | 3 | 5 | 37.5% | 1.6082 | 2.0615 | 0.2577 | NOISE |

### By Direction

| By Direction | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| short | 8 | 1 | 7 | 12.5% | 0.5866 | -2.0798 | -0.26 | IMPORTANT |
| long | 11 | 6 | 5 | 54.55% | 1.5148 | 2.574 | 0.234 | NOISE |

### By Market Regime

| By Market Regime | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| RANGING | 8 | 2 | 6 | 25.0% | 0.3195 | -4.0828 | -0.5103 | IMPORTANT |
| HIGH_VOLATILITY | 6 | 2 | 4 | 33.33% | 1.9455 | 1.9202 | 0.32 | NOISE |
| TRENDING | 5 | 3 | 2 | 60.0% | 2.3284 | 2.6568 | 0.5314 | NOISE |

### By Setup Type

| By Setup Type | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SECONDARY_SIGNAL | 6 | 2 | 4 | 33.33% | 0.9407 | -0.1204 | -0.0201 | IMPORTANT |
| MAIN_SIGNAL | 13 | 5 | 8 | 38.46% | 1.0768 | 0.6146 | 0.0473 | NOISE |

### By Entry Context

| By Entry Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| CHOPPY_RANGE | 4 | 1 | 3 | 25.0% | 0.1368 | -2.5896 | -0.6474 | WATCH |
| EXHAUSTION | 3 | 1 | 2 | 33.33% | 0.8284 | -0.3432 | -0.1144 | WATCH |
| BREAKOUT | 8 | 3 | 5 | 37.5% | 1.3198 | 0.9692 | 0.1212 | NOISE |
| PULLBACK | 4 | 2 | 2 | 50.0% | 2.2289 | 2.4578 | 0.6144 | NOISE |

### By Liquidity Context

| By Liquidity Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| location:near_support | 5 | 1 | 4 | 20.0% | 0.3767 | -2.4932 | -0.4986 | IMPORTANT |
| location:premium_zone | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | WATCH |
| location:discount_zone | 3 | 1 | 2 | 33.33% | 1.2183 | 0.1792 | 0.0597 | NOISE |
| location:mid_range | 5 | 2 | 3 | 40.0% | 1.4284 | 0.9468 | 0.1894 | NOISE |
| location:near_resistance | 3 | 2 | 1 | 66.67% | 4.451 | 3.451 | 1.1503 | NOISE |

### By Trend Alignment

| By Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_bullish | 8 | 1 | 7 | 12.5% | 0.5866 | -2.0798 | -0.26 | IMPORTANT |
| aligned_bearish | 8 | 3 | 5 | 37.5% | 0.7148 | -1.426 | -0.1783 | IMPORTANT |
| mixed_bullish_vs_bearish | 3 | 3 | 0 | 100.0% | inf | 4.0 | 1.3333 | NOISE |

### By Score Bucket

| By Score Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 90+ | 2 | 0 | 2 | 0.0% | 0.0 | -1.6413 | -0.8206 | NOISE |
| 80-89 | 4 | 1 | 3 | 25.0% | 0.2954 | -0.9791 | -0.2448 | WATCH |
| <60 | 10 | 4 | 6 | 40.0% | 1.243 | 1.4578 | 0.1458 | NOISE |
| 60-69 | 3 | 2 | 1 | 66.67% | 2.6568 | 1.6568 | 0.5523 | NOISE |

### By Penalty

| By Penalty | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 19 | 7 | 12 | 36.84% | 1.0493 | 0.4942 | 0.026 | NOISE |

### By Other Warning

| By Other Warning | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| low_volume | 4 | 1 | 3 | 25.0% | 0.1368 | -2.5896 | -0.6474 | WATCH |
| dirty_sideways_market | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | WATCH |
| none | 15 | 6 | 9 | 40.0% | 1.4386 | 3.0838 | 0.2056 | NOISE |

## Recommended Action

KEEP
