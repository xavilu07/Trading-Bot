# SCORE_80_89_REGIME_DECOMPOSITION

Generated at: 2026-06-05T16:46:27+00:00
Data path: data
Method: Exclude bullish_sweep first, then compare score 80-89 TRENDING vs RANGING.

## Executive Summary

- Score 80-89 total: trades=5, WR=40.0%, PF=1.3749, TotalR=0.5209, AvgR=0.1042
- TRENDING: trades=1, WR=0.0%, PF=0.0, TotalR=-1.0, AvgR=-1.0
- RANGING: trades=2, WR=100.0%, PF=inf, TotalR=1.9104, AvgR=0.9552
- Why does TRENDING lose money? TRENDING metrics are trades=1, WR=0.0%, PF=0.0, TotalR=-1.0, AvgR=-1.0 with no 10-trade toxic subgroup.
- Why does RANGING survive? RANGING metrics are trades=2, WR=100.0%, PF=inf, TotalR=1.9104, AvgR=0.9552 but no survivor met 10-trade criteria.
- Main difference subgroup: trend_alignment=aligned_bearish (TRENDING TotalR=-1.0, RANGING TotalR=1.9104, gap=2.9104)
- PF if worst TRENDING subgroup removed: 1.3749
- Future shadow filter evidence: NO

## Regime Difference Analysis

| Dimension | Winner TRENDING | Loser TRENDING | Winner RANGING | Loser RANGING | Largest Gap |
|---|---|---|---|---|---|
| symbol | BNBUSDT TotalR=-1.0 PF=0.0 | BNBUSDT TotalR=-1.0 PF=0.0 | BNBUSDT TotalR=1.5 PF=inf | AVAXUSDT TotalR=0.4104 PF=inf | symbol=BNBUSDT (TRENDING TotalR=-1.0, RANGING TotalR=1.5, gap=2.5) |
| session | OVERLAP TotalR=-1.0 PF=0.0 | OVERLAP TotalR=-1.0 PF=0.0 | LONDON TotalR=1.5 PF=inf | NEW_YORK TotalR=0.4104 PF=inf | session=LONDON (TRENDING TotalR=0.0, RANGING TotalR=1.5, gap=1.5) |
| direction | long TotalR=-1.0 PF=0.0 | long TotalR=-1.0 PF=0.0 | short TotalR=1.5 PF=inf | long TotalR=0.4104 PF=inf | direction=short (TRENDING TotalR=0.0, RANGING TotalR=1.5, gap=1.5) |
| setup_type | MAIN_SIGNAL TotalR=-1.0 PF=0.0 | MAIN_SIGNAL TotalR=-1.0 PF=0.0 | SECONDARY_SIGNAL TotalR=1.9104 PF=inf | SECONDARY_SIGNAL TotalR=1.9104 PF=inf | setup_type=SECONDARY_SIGNAL (TRENDING TotalR=0.0, RANGING TotalR=1.9104, gap=1.9104) |
| entry_context | PULLBACK TotalR=-1.0 PF=0.0 | PULLBACK TotalR=-1.0 PF=0.0 | BREAKOUT TotalR=1.5 PF=inf | CHOPPY_RANGE TotalR=0.4104 PF=inf | entry_context=BREAKOUT (TRENDING TotalR=0.0, RANGING TotalR=1.5, gap=1.5) |
| liquidity_context | location:near_support TotalR=-1.0 PF=0.0 | location:near_support TotalR=-1.0 PF=0.0 | location:near_support TotalR=1.5 PF=inf | location:premium_zone TotalR=0.4104 PF=inf | liquidity_context=location:near_support (TRENDING TotalR=-1.0, RANGING TotalR=1.5, gap=2.5) |
| warning | against_htf TotalR=-1.0 PF=0.0 | against_htf TotalR=-1.0 PF=0.0 | none TotalR=1.5 PF=inf | against_htf TotalR=0.4104 PF=inf | warning=none (TRENDING TotalR=0.0, RANGING TotalR=1.5, gap=1.5) |
| penalty | none TotalR=-1.0 PF=0.0 | none TotalR=-1.0 PF=0.0 | none TotalR=1.9104 PF=inf | none TotalR=1.9104 PF=inf | penalty=none (TRENDING TotalR=-1.0, RANGING TotalR=1.9104, gap=2.9104) |
| rejection_reason | body_ratio_below_threshold TotalR=-1.0 PF=0.0 | body_ratio_below_threshold TotalR=-1.0 PF=0.0 | directional_confluence_failed TotalR=1.9104 PF=inf | directional_confluence_failed TotalR=1.9104 PF=inf | rejection_reason=directional_confluence_failed (TRENDING TotalR=0.0, RANGING TotalR=1.9104, gap=1.9104) |
| trend_alignment | aligned_bearish TotalR=-1.0 PF=0.0 | aligned_bearish TotalR=-1.0 PF=0.0 | aligned_bearish TotalR=1.9104 PF=inf | aligned_bearish TotalR=1.9104 PF=inf | trend_alignment=aligned_bearish (TRENDING TotalR=-1.0, RANGING TotalR=1.9104, gap=2.9104) |
| htf_alignment | against_htf TotalR=-1.0 PF=0.0 | against_htf TotalR=-1.0 PF=0.0 | aligned_with_htf TotalR=1.5 PF=inf | against_htf TotalR=0.4104 PF=inf | htf_alignment=aligned_with_htf (TRENDING TotalR=0.0, RANGING TotalR=1.5, gap=1.5) |

## Toxic TRENDING Subgroups

Criteria: minimum 10 trades, negative Total R, PF < 1.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

## Safe RANGING Survivors

Criteria: minimum 10 trades, PF > 1.1, positive Total R.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

## Top TRENDING Subgroup Removal Counterfactual

- Removed subgroup: none
- Removed metrics: trades=0, WR=0.0%, PF=0.0, TotalR=0.0, AvgR=0.0
- Remaining metrics: trades=5, WR=40.0%, PF=1.3749, TotalR=0.5209, AvgR=0.1042

## TRENDING Breakdowns

### By Symbol

| By Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| BNBUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By Session

| By Session | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| OVERLAP | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By Direction

| By Direction | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| long | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By Setup Type

| By Setup Type | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| MAIN_SIGNAL | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By Entry Context

| By Entry Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| PULLBACK | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By Liquidity Context

| By Liquidity Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| location:near_support | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By Warning

| By Warning | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| against_htf | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By Penalty

| By Penalty | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By Rejection Reason

| By Rejection Reason | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| body_ratio_below_threshold | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By Trend Alignment

| By Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_bearish | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By HTF Alignment

| By HTF Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| against_htf | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

## RANGING Breakdowns

### By Symbol

| By Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| AVAXUSDT | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| BNBUSDT | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |

### By Session

| By Session | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| NEW_YORK | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| LONDON | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |

### By Direction

| By Direction | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| long | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| short | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |

### By Setup Type

| By Setup Type | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SECONDARY_SIGNAL | 2 | 2 | 0 | 100.0% | inf | 1.9104 | 0.9552 | NOISE |

### By Entry Context

| By Entry Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| CHOPPY_RANGE | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| BREAKOUT | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |

### By Liquidity Context

| By Liquidity Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| location:premium_zone | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| location:near_support | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |

### By Warning

| By Warning | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| against_htf | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| dirty_sideways_market | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| low_volume | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| none | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |

### By Penalty

| By Penalty | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 2 | 2 | 0 | 100.0% | inf | 1.9104 | 0.9552 | NOISE |

### By Rejection Reason

| By Rejection Reason | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| directional_confluence_failed | 2 | 2 | 0 | 100.0% | inf | 1.9104 | 0.9552 | NOISE |
| market_structure_range_penalty | 2 | 2 | 0 | 100.0% | inf | 1.9104 | 0.9552 | NOISE |
| secondary_setup_requirements_failed | 2 | 2 | 0 | 100.0% | inf | 1.9104 | 0.9552 | NOISE |

### By Trend Alignment

| By Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_bearish | 2 | 2 | 0 | 100.0% | inf | 1.9104 | 0.9552 | NOISE |

### By HTF Alignment

| By HTF Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| against_htf | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| aligned_with_htf | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |

## Next Recommended Investigation

Deep dive regime gap `trend_alignment=aligned_bearish`.
