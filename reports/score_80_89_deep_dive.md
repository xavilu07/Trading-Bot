# SCORE_80_89_DEEP_DIVE

Generated at: 2026-06-05T16:13:53+00:00
Data path: data
Method: Exclude bullish_sweep first, then analyze trades with 80 <= score < 90.
Classification: NOISE

## Executive Summary

- Score 80-89: trades=5, WR=40.0%, PF=1.3749, TotalR=0.5209, AvgR=0.1042
- Is entire 80-89 bucket bad? NO
- Main loss subgroup: session=OVERLAP (trades=1, PF=0.0, TotalR=-1.0, class=NOISE)
- PF if main subgroup removed: 4.9047
- Safe survivor worth keeping: none
- Recommended action: KEEP

## Toxic Subgroups

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| session | OVERLAP | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| market_regime | TRENDING | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| setup_type | MAIN_SIGNAL | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| entry_context | PULLBACK | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| rejection_reason | body_ratio_below_threshold | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| warning | against_htf | 4 | 1 | 3 | 25.0% | 0.2954 | -0.9791 | -0.2448 | WATCH |
| htf_alignment | against_htf | 4 | 1 | 3 | 25.0% | 0.2954 | -0.9791 | -0.2448 | WATCH |
| direction | long | 2 | 1 | 1 | 50.0% | 0.4104 | -0.5896 | -0.2948 | NOISE |
| market_regime | HIGH_VOLATILITY | 2 | 0 | 2 | 0.0% | 0.0 | -0.3895 | -0.1947 | NOISE |
| trend_alignment | aligned_bullish | 2 | 0 | 2 | 0.0% | 0.0 | -0.3895 | -0.1947 | NOISE |
| symbol | DOGEUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -0.21 | -0.21 | NOISE |
| liquidity_context | location:mid_range | 1 | 0 | 1 | 0.0% | 0.0 | -0.21 | -0.21 | NOISE |
| symbol | ETHUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -0.1795 | -0.1795 | NOISE |
| liquidity_context | location:discount_zone | 1 | 0 | 1 | 0.0% | 0.0 | -0.1795 | -0.1795 | NOISE |

## Survivors Inside 80-89

Criteria: minimum 10 trades, PF > 1.10, positive Total R.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

## Top Subgroup Removal Counterfactual

- Removed subgroup: session=OVERLAP
- Removed metrics: trades=1, WR=0.0%, PF=0.0, TotalR=-1.0, AvgR=-1.0
- Remaining metrics: trades=4, WR=50.0%, PF=4.9047, TotalR=1.5209, AvgR=0.3802

## Breakdowns

### By Symbol

| By Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| DOGEUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -0.21 | -0.21 | NOISE |
| ETHUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -0.1795 | -0.1795 | NOISE |
| AVAXUSDT | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| BNBUSDT | 2 | 1 | 1 | 50.0% | 1.5 | 0.5 | 0.25 | NOISE |

### By Session

| By Session | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| OVERLAP | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| NEW_YORK | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| LONDON | 3 | 1 | 2 | 33.33% | 3.8511 | 1.1105 | 0.3702 | NOISE |

### By Market Regime

| By Market Regime | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| TRENDING | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| HIGH_VOLATILITY | 2 | 0 | 2 | 0.0% | 0.0 | -0.3895 | -0.1947 | NOISE |
| RANGING | 2 | 2 | 0 | 100.0% | inf | 1.9104 | 0.9552 | NOISE |

### By Setup Type

| By Setup Type | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| MAIN_SIGNAL | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SECONDARY_SIGNAL | 4 | 2 | 2 | 50.0% | 4.9047 | 1.5209 | 0.3802 | NOISE |

### By Direction

| By Direction | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| long | 2 | 1 | 1 | 50.0% | 0.4104 | -0.5896 | -0.2948 | NOISE |
| short | 3 | 1 | 2 | 33.33% | 3.8511 | 1.1105 | 0.3702 | NOISE |

### By Entry Context

| By Entry Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| PULLBACK | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| CHOPPY_RANGE | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| BREAKOUT | 3 | 1 | 2 | 33.33% | 3.8511 | 1.1105 | 0.3702 | NOISE |

### By Liquidity Context

| By Liquidity Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| location:mid_range | 1 | 0 | 1 | 0.0% | 0.0 | -0.21 | -0.21 | NOISE |
| location:discount_zone | 1 | 0 | 1 | 0.0% | 0.0 | -0.1795 | -0.1795 | NOISE |
| location:premium_zone | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| location:near_support | 2 | 1 | 1 | 50.0% | 1.5 | 0.5 | 0.25 | NOISE |

### By Warning

| By Warning | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| against_htf | 4 | 1 | 3 | 25.0% | 0.2954 | -0.9791 | -0.2448 | WATCH |
| dirty_sideways_market | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| low_volume | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| none | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |

### By Penalty

| By Penalty | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 5 | 2 | 3 | 40.0% | 1.3749 | 0.5209 | 0.1042 | NOISE |

### By Rejection Reason

| By Rejection Reason | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| body_ratio_below_threshold | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| directional_confluence_failed | 4 | 2 | 2 | 50.0% | 4.9047 | 1.5209 | 0.3802 | NOISE |
| market_structure_range_penalty | 4 | 2 | 2 | 50.0% | 4.9047 | 1.5209 | 0.3802 | NOISE |
| secondary_setup_requirements_failed | 4 | 2 | 2 | 50.0% | 4.9047 | 1.5209 | 0.3802 | NOISE |

### By Trend Alignment

| By Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_bullish | 2 | 0 | 2 | 0.0% | 0.0 | -0.3895 | -0.1947 | NOISE |
| aligned_bearish | 3 | 2 | 1 | 66.67% | 1.9104 | 0.9104 | 0.3035 | NOISE |

### By HTF Alignment

| By HTF Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| against_htf | 4 | 1 | 3 | 25.0% | 0.2954 | -0.9791 | -0.2448 | WATCH |
| aligned_with_htf | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |

## Counterfactual Recommendation

Keep score 80-89 active; current evidence is not negative.
