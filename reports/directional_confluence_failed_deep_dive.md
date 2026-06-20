# DIRECTIONAL_CONFLUENCE_FAILED_DEEP_DIVE

Generated at: 2026-06-08T16:25:50+00:00
Data path: data
Method: Analyze canonical closed trades tagged with directional_confluence_failed in warnings, penalties, reasons, conditions_failed or rejection_reasons.
Classification: IMPORTANT

## Executive Summary

- Baseline: trades=40, WR=32.5%, PF=0.8439, TotalR=-3.5754, AvgR=-0.0894
- directional_confluence_failed: trades=13, WR=23.08%, PF=0.3876, TotalR=-4.5979, AvgR=-0.3537
- Is globally toxic? YES
- Biggest loss contributor: score_bucket=<60 (trades=5, PF=0.0, TotalR=-4.4775, class=IMPORTANT)
- Best survivor: none
- Would removal improve PF materially? YES
- Recommended action: SHADOW_BLOCK

## Toxic Subgroups

Criteria: minimum 5 trades, negative Total R, PF < 1.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| score_bucket | <60 | 5 | 0 | 5 | 0.0% | 0.0 | -4.4775 | -0.8955 | IMPORTANT |
| rejection_reason | distance_to_liquidity_penalty | 5 | 0 | 5 | 0.0% | 0.0 | -4.4775 | -0.8955 | IMPORTANT |
| market_regime | HIGH_VOLATILITY | 5 | 0 | 5 | 0.0% | 0.0 | -3.0308 | -0.6062 | IMPORTANT |
| htf_alignment | against_htf | 9 | 1 | 8 | 11.11% | 0.0681 | -5.6204 | -0.6245 | IMPORTANT |
| warning | against_htf | 9 | 1 | 8 | 11.11% | 0.0681 | -5.6204 | -0.6245 | IMPORTANT |
| trend_alignment | aligned_bullish | 8 | 1 | 7 | 12.5% | 0.1988 | -4.0308 | -0.5039 | IMPORTANT |
| setup_type | MAIN_SIGNAL | 6 | 1 | 5 | 16.67% | 0.2 | -4.0 | -0.6667 | IMPORTANT |
| direction | short | 8 | 1 | 7 | 12.5% | 0.3327 | -3.0083 | -0.376 | IMPORTANT |
| penalty | none | 13 | 3 | 10 | 23.08% | 0.3876 | -4.5979 | -0.3537 | IMPORTANT |
| rejection_reason | directional_confluence_failed | 13 | 3 | 10 | 23.08% | 0.3876 | -4.5979 | -0.3537 | IMPORTANT |
| direction | long | 5 | 2 | 3 | 40.0% | 0.4701 | -1.5896 | -0.3179 | IMPORTANT |
| entry_context | BREAKOUT | 9 | 2 | 7 | 22.22% | 0.5545 | -2.0083 | -0.2231 | IMPORTANT |
| rejection_reason | market_structure_range_penalty | 10 | 3 | 7 | 30.0% | 0.598 | -1.9566 | -0.1957 | IMPORTANT |
| session | LONDON | 8 | 2 | 6 | 25.0% | 0.6465 | -1.367 | -0.1709 | IMPORTANT |
| market_regime | RANGING | 8 | 3 | 5 | 37.5% | 0.65 | -1.5671 | -0.1959 | IMPORTANT |
| setup_type | SECONDARY_SIGNAL | 7 | 2 | 5 | 28.57% | 0.7616 | -0.5979 | -0.0854 | IMPORTANT |
| rejection_reason | secondary_setup_requirements_failed | 7 | 2 | 5 | 28.57% | 0.7616 | -0.5979 | -0.0854 | IMPORTANT |
| trend_alignment | aligned_bearish | 5 | 2 | 3 | 40.0% | 0.7711 | -0.5671 | -0.1134 | IMPORTANT |

## Survivors

Criteria: minimum 5 trades, PF > 1.1, positive Total R.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

## Counterfactual Removal

- PF current: 0.8439
- PF without directional_confluence_failed: 1.0664
- TotalR current: -3.5754
- TotalR without directional_confluence_failed: 1.0225
- Winrate delta: 4.54
- Trades removed: 13

## Impact Ranking

| Dimension | Value | Removed Trades | PF Before | PF After | TotalR Before | TotalR After | R Improvement | PF Improvement |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| htf_alignment | against_htf | 9 | 0.3876 | 1.692 | -4.5979 | 1.0225 | 5.6204 | 1.3044 |
| warning | against_htf | 9 | 0.3876 | 1.692 | -4.5979 | 1.0225 | 5.6204 | 1.3044 |
| rejection_reason | directional_confluence_failed | 13 | 0.3876 | 0.0 | -4.5979 | 0.0 | 4.5979 | -0.3876 |
| score_bucket | <60 | 5 | 0.3876 | 0.9603 | -4.5979 | -0.1204 | 4.4775 | 0.5727 |
| rejection_reason | distance_to_liquidity_penalty | 5 | 0.3876 | 0.9603 | -4.5979 | -0.1204 | 4.4775 | 0.5727 |
| trend_alignment | aligned_bullish | 8 | 0.3876 | 0.7711 | -4.5979 | -0.5671 | 4.0308 | 0.3835 |
| setup_type | MAIN_SIGNAL | 6 | 0.3876 | 0.7616 | -4.5979 | -0.5979 | 4.0 | 0.374 |
| market_regime | HIGH_VOLATILITY | 5 | 0.3876 | 0.65 | -4.5979 | -1.5671 | 3.0308 | 0.2624 |
| direction | short | 8 | 0.3876 | 0.4701 | -4.5979 | -1.5896 | 3.0083 | 0.0825 |
| score_bucket | 90+ | 3 | 0.3876 | 0.598 | -4.5979 | -1.9566 | 2.6413 | 0.2104 |
| entry_context | BREAKOUT | 9 | 0.3876 | 0.1368 | -4.5979 | -2.5896 | 2.0083 | -0.2508 |
| rejection_reason | market_structure_range_penalty | 10 | 0.3876 | 0.0 | -4.5979 | -2.6413 | 1.9566 | -0.3876 |
| symbol | DOGEUSDT | 3 | 0.3876 | 0.5145 | -4.5979 | -2.7466 | 1.8513 | 0.1269 |
| session | OVERLAP | 2 | 0.3876 | 0.4961 | -4.5979 | -2.9566 | 1.6413 | 0.1085 |
| session | NEW_YORK | 3 | 0.3876 | 0.4539 | -4.5979 | -3.0083 | 1.5896 | 0.0663 |
| entry_context | CHOPPY_RANGE | 3 | 0.3876 | 0.4539 | -4.5979 | -3.0083 | 1.5896 | 0.0663 |
| warning | low_volume | 3 | 0.3876 | 0.4539 | -4.5979 | -3.0083 | 1.5896 | 0.0663 |
| direction | long | 5 | 0.3876 | 0.3327 | -4.5979 | -3.0083 | 1.5896 | -0.0549 |
| market_regime | RANGING | 8 | 0.3876 | 0.0 | -4.5979 | -3.0308 | 1.5671 | -0.3876 |
| liquidity_context | location:near_support | 4 | 0.3876 | 0.3128 | -4.5979 | -3.0979 | 1.5 | -0.0748 |
| symbol | XRPUSDT | 2 | 0.3876 | 0.4826 | -4.5979 | -3.1204 | 1.4775 | 0.095 |
| session | LONDON | 8 | 0.3876 | 0.1127 | -4.5979 | -3.2309 | 1.367 | -0.2749 |
| liquidity_context | location:mid_range | 2 | 0.3876 | 0.4621 | -4.5979 | -3.3879 | 1.21 | 0.0745 |
| symbol | ETHUSDT | 2 | 0.3876 | 0.4599 | -4.5979 | -3.4184 | 1.1795 | 0.0723 |
| symbol | APEUSDT | 1 | 0.3876 | 0.4472 | -4.5979 | -3.5979 | 1.0 | 0.0596 |
| symbol | SOLUSDT | 1 | 0.3876 | 0.4472 | -4.5979 | -3.5979 | 1.0 | 0.0596 |
| symbol | TRXUSDT | 1 | 0.3876 | 0.4472 | -4.5979 | -3.5979 | 1.0 | 0.0596 |
| entry_context | EXHAUSTION | 1 | 0.3876 | 0.4472 | -4.5979 | -3.5979 | 1.0 | 0.0596 |
| liquidity_context | location:near_resistance | 1 | 0.3876 | 0.4472 | -4.5979 | -3.5979 | 1.0 | 0.0596 |
| setup_type | SECONDARY_SIGNAL | 7 | 0.3876 | 0.2 | -4.5979 | -4.0 | 0.5979 | -0.1876 |

## Breakdowns

### By Symbol

| By Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| DOGEUSDT | 3 | 0 | 3 | 0.0% | 0.0 | -1.8513 | -0.6171 | WATCH |
| XRPUSDT | 2 | 0 | 2 | 0.0% | 0.0 | -1.4775 | -0.7388 | NOISE |
| ETHUSDT | 2 | 0 | 2 | 0.0% | 0.0 | -1.1795 | -0.5897 | NOISE |
| APEUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SOLUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| TRXUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| AVAXUSDT | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| BTCUSDT | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| BNBUSDT | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |

### By Session

| By Session | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| OVERLAP | 2 | 0 | 2 | 0.0% | 0.0 | -1.6413 | -0.8206 | NOISE |
| NEW_YORK | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | WATCH |
| LONDON | 8 | 2 | 6 | 25.0% | 0.6465 | -1.367 | -0.1709 | IMPORTANT |

### By Direction

| By Direction | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| short | 8 | 1 | 7 | 12.5% | 0.3327 | -3.0083 | -0.376 | IMPORTANT |
| long | 5 | 2 | 3 | 40.0% | 0.4701 | -1.5896 | -0.3179 | IMPORTANT |

### By Setup Type

| By Setup Type | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| MAIN_SIGNAL | 6 | 1 | 5 | 16.67% | 0.2 | -4.0 | -0.6667 | IMPORTANT |
| SECONDARY_SIGNAL | 7 | 2 | 5 | 28.57% | 0.7616 | -0.5979 | -0.0854 | IMPORTANT |

### By Entry Context

| By Entry Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| BREAKOUT | 9 | 2 | 7 | 22.22% | 0.5545 | -2.0083 | -0.2231 | IMPORTANT |
| CHOPPY_RANGE | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | WATCH |
| EXHAUSTION | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

### By Liquidity Context

| By Liquidity Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| location:near_support | 4 | 1 | 3 | 25.0% | 0.5 | -1.5 | -0.375 | WATCH |
| location:mid_range | 2 | 0 | 2 | 0.0% | 0.0 | -1.21 | -0.605 | NOISE |
| location:near_resistance | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| location:premium_zone | 2 | 1 | 1 | 50.0% | 0.4104 | -0.5896 | -0.2948 | NOISE |
| location:discount_zone | 4 | 1 | 3 | 25.0% | 0.7702 | -0.2983 | -0.0746 | WATCH |

### By Market Regime

| By Market Regime | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| HIGH_VOLATILITY | 5 | 0 | 5 | 0.0% | 0.0 | -3.0308 | -0.6062 | IMPORTANT |
| RANGING | 8 | 3 | 5 | 37.5% | 0.65 | -1.5671 | -0.1959 | IMPORTANT |

### By Trend Alignment

| By Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_bullish | 8 | 1 | 7 | 12.5% | 0.1988 | -4.0308 | -0.5039 | IMPORTANT |
| aligned_bearish | 5 | 2 | 3 | 40.0% | 0.7711 | -0.5671 | -0.1134 | IMPORTANT |

### By HTF Alignment

| By HTF Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| against_htf | 9 | 1 | 8 | 11.11% | 0.0681 | -5.6204 | -0.6245 | IMPORTANT |
| aligned_with_htf | 4 | 2 | 2 | 50.0% | 1.692 | 1.0225 | 0.2556 | NOISE |

### By Score Bucket

| By Score Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| <60 | 5 | 0 | 5 | 0.0% | 0.0 | -4.4775 | -0.8955 | IMPORTANT |
| 90+ | 3 | 0 | 3 | 0.0% | 0.0 | -2.6413 | -0.8804 | WATCH |
| 70-79 | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| 80-89 | 4 | 2 | 2 | 50.0% | 4.9047 | 1.5209 | 0.3802 | NOISE |

### By Warning

| By Warning | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| against_htf | 9 | 1 | 8 | 11.11% | 0.0681 | -5.6204 | -0.6245 | IMPORTANT |
| low_volume | 3 | 1 | 2 | 33.33% | 0.2052 | -1.5896 | -0.5299 | WATCH |
| dirty_sideways_market | 2 | 1 | 1 | 50.0% | 0.4104 | -0.5896 | -0.2948 | NOISE |
| none | 4 | 2 | 2 | 50.0% | 1.692 | 1.0225 | 0.2556 | NOISE |

### By Penalty

| By Penalty | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 13 | 3 | 10 | 23.08% | 0.3876 | -4.5979 | -0.3537 | IMPORTANT |

### By Rejection Reason

| By Rejection Reason | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| directional_confluence_failed | 13 | 3 | 10 | 23.08% | 0.3876 | -4.5979 | -0.3537 | IMPORTANT |
| distance_to_liquidity_penalty | 5 | 0 | 5 | 0.0% | 0.0 | -4.4775 | -0.8955 | IMPORTANT |
| market_structure_range_penalty | 10 | 3 | 7 | 30.0% | 0.598 | -1.9566 | -0.1957 | IMPORTANT |
| secondary_setup_requirements_failed | 7 | 2 | 5 | 28.57% | 0.7616 | -0.5979 | -0.0854 | IMPORTANT |

## Recommended Action

SHADOW_BLOCK
