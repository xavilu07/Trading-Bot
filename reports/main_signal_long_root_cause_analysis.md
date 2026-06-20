# MAIN_SIGNAL_LONG_ROOT_CAUSE_ANALYSIS

Generated at: 2026-06-09T17:46:20+00:00
Data path: data
Method: Analyze canonical closed trades where setup_type=MAIN_SIGNAL and direction=long, then discount already blocked bullish_sweep and against_htf+BREAKOUT contexts.
Classification: NOISE
Recommended action: KEEP

## Executive Summary

- Global baseline: trades=40, WR=32.5%, PF=0.8439, TotalR=-3.5754, AvgR=-0.0894
- MAIN_SIGNAL LONG baseline: trades=14, WR=50.0%, PF=1.7027, TotalR=4.9188, AvgR=0.3513
- Existing blocks covered: trades=3, WR=66.6667%, PF=2.5, TotalR=1.5, AvgR=0.5
- Remaining after existing blocks: trades=11, WR=45.4545%, PF=1.5698, TotalR=3.4188, AvgR=0.3108
- Toxicity already covered R: 0.0
- Remaining toxic R: 0.0
- Is MAIN_SIGNAL LONG globally toxic? NO
- Still toxic after existing blocks? NO
- Next best non-overlapping root cause: none
- Smallest high-impact rule: none
- Dominant issue: liquidity_sweep

## MAIN_SIGNAL LONG Baseline

| Trades | Wins | Losses | WR | PF | Total R | Avg R |
|---:|---:|---:|---:|---:|---:|---:|
| 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 |

## Comparisons

| Group | Trades | Wins | Losses | WR | PF | Total R | Avg R | Top Symbol | Top Session | Top Regime | Top Entry | Top Liquidity | Top HTF |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|
| MAIN_SIGNAL_LONG | 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 | SOLUSDT (21.4286%) | OVERLAP (57.1429%) | RANGING (42.8571%) | BREAKOUT (50.0%) | none (100.0%) | against_htf (64.2857%) |
| MAIN_SIGNAL_SHORT | 8 | 1 | 7 | 12.5% | 0.4216 | -4.049 | -0.5061 | ETHUSDT (12.5%) | NEW_YORK (62.5%) | RANGING (50.0%) | PULLBACK (50.0%) | none (100.0%) | against_htf (50.0%) |
| SECONDARY_SIGNAL_LONG | 5 | 3 | 2 | 60.0% | 2.0161 | 1.3062 | 0.2612 | ETHUSDT (40.0%) | NEW_YORK (60.0%) | TRENDING (40.0%) | BREAKOUT (80.0%) | none (100.0%) | aligned_with_htf (60.0%) |
| NON_MAIN_SIGNAL_LONG | 26 | 6 | 20 | 23.0769% | 0.4659 | -8.4942 | -0.3267 | DOGEUSDT (15.3846%) | NEW_YORK (42.3077%) | RANGING (46.1538%) | BREAKOUT (61.5385%) | none (100.0%) | aligned_with_htf (61.5385%) |

## Toxic Root Causes

Criteria: minimum 10 closed trades, PF < 0.85, TotalR < 0. Ranked by R improvement, damage and collateral.

| Rule | Factors | Removed | Removed PF | Removed TotalR | PF After | TotalR After | R Improvement | Profitable Lost | Losing Removed | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

## Toxic Single-Factor Clusters

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |

## Survivor Longs

Criteria: minimum 10 closed trades, PF > 1.1 and TotalR > 0.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| liquidity_sweep | none | 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 | NOISE |
| body_ratio_bucket | UNKNOWN | 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 | NOISE |
| penalty | none | 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 | NOISE |
| failed_filter | none | 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 | NOISE |
| volume_ratio_bucket | volume_high | 10 | 5 | 5 | 50.0% | 1.8824 | 4.412 | 0.4412 | NOISE |
| distance_to_liquidity_bucket | distance_close | 10 | 4 | 6 | 40.0% | 1.377 | 2.262 | 0.2262 | NOISE |

## Tiny But Promising Longs

Criteria: 5-9 closed trades, PF > 1.3 and TotalR > 0.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| rr_bucket | rr_1_5_to_2 | 6 | 5 | 1 | 83.3333% | 6.6636 | 5.6636 | 0.9439 | NOISE |
| score_bucket | 60-69 | 5 | 3 | 2 | 60.0% | 3.456 | 4.912 | 0.9824 | NOISE |
| entry_context | BREAKOUT | 7 | 4 | 3 | 57.1429% | 2.5851 | 4.7552 | 0.6793 | NOISE |
| market_regime | TRENDING | 6 | 3 | 3 | 50.0% | 2.4707 | 4.412 | 0.7353 | NOISE |
| htf_alignment | aligned_with_htf | 5 | 3 | 2 | 60.0% | 3.1276 | 4.2552 | 0.851 | NOISE |
| session | LONDON | 5 | 4 | 1 | 80.0% | 4.5 | 3.5 | 0.7 | NOISE |
| rejection_reason | distance_to_liquidity_penalty | 7 | 3 | 4 | 42.8571% | 1.853 | 3.412 | 0.4874 | NOISE |
| condition_failed | distance_to_liquidity_penalty | 7 | 3 | 4 | 42.8571% | 1.853 | 3.412 | 0.4874 | NOISE |
| rejection_reason | body_ratio_below_threshold | 7 | 4 | 3 | 57.1429% | 1.8879 | 2.6636 | 0.3805 | NOISE |
| condition_failed | body_ratio_below_threshold | 7 | 4 | 3 | 57.1429% | 1.8879 | 2.6636 | 0.3805 | NOISE |
| session | OVERLAP | 8 | 3 | 5 | 37.5% | 1.4838 | 2.4188 | 0.3024 | NOISE |
| rejection_reason | market_structure_range_penalty | 7 | 4 | 3 | 57.1429% | 1.5023 | 1.5068 | 0.2153 | NOISE |
| condition_failed | market_structure_range_penalty | 7 | 4 | 3 | 57.1429% | 1.5023 | 1.5068 | 0.2153 | NOISE |
| score_bucket | <60 | 6 | 3 | 3 | 50.0% | 1.3356 | 1.0068 | 0.1678 | NOISE |

## Counterfactuals

| Scenario | Removed | PF Before | PF After | TotalR Before | TotalR After | R Improvement | WR Delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| without_all_main_signal_long | 14 | 0.8439 | 0.4659 | -3.5754 | -8.4942 | -4.9188 | -9.4231 |
| none | 0 | 0.8439 | 0.8439 | -3.5754 | -3.5754 | 0.0 | 0.0 |
| none | 0 | 0.8439 | 0.8439 | -3.5754 | -3.5754 | 0.0 | 0.0 |
| without_bullish_sweep_already_blocked_contexts | 0 | 0.8439 | 0.8439 | -3.5754 | -3.5754 | 0.0 | 0.0 |
| without_against_htf_breakout_already_blocked_contexts | 8 | 0.8439 | 0.7713 | -3.5754 | -4.5446 | -0.9692 | -1.25 |
| without_existing_production_blocks | 8 | 0.8439 | 0.7713 | -3.5754 | -4.5446 | -0.9692 | -1.25 |
| without_remaining_toxic_main_signal_long_after_existing_blocks | 11 | 0.8439 | 0.5862 | -3.5754 | -6.9942 | -3.4188 | -4.9138 |

## Tested Root Cause Rules

| Rule | Factors | Removed | Removed PF | Removed TotalR | PF After | TotalR After | R Improvement | Profitable Lost | Losing Removed | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| MAIN_SIGNAL LONG + against_htf + near_support | against_htf, near_support | 5 | 0.3767 | -2.4932 | 0.9428 | -1.0822 | 2.4932 | 1 | 4 | WATCH |
| MAIN_SIGNAL LONG + directional_confluence_failed | directional_confluence_failed | 4 | 0.3333 | -2.0 | 0.9208 | -1.5754 | 2.0 | 1 | 3 | NOISE |
| MAIN_SIGNAL LONG + HIGH_VOLATILITY + near_support | HIGH_VOLATILITY, near_support | 1 | 0.0 | -1.0 | 0.8824 | -2.5754 | 1.0 | 0 | 1 | NOISE |
| MAIN_SIGNAL LONG + score_bucket 90+ | score_bucket 90+ | 1 | 0.0 | -1.0 | 0.8824 | -2.5754 | 1.0 | 0 | 1 | NOISE |
| MAIN_SIGNAL LONG + bullish_sweep | bullish_sweep | 0 | 0.0 | 0.0 | 0.8439 | -3.5754 | 0.0 | 0 | 0 | NOISE |
| MAIN_SIGNAL LONG + bullish_sweep + against_htf | bullish_sweep, against_htf | 0 | 0.0 | 0.0 | 0.8439 | -3.5754 | 0.0 | 0 | 0 | NOISE |
| MAIN_SIGNAL LONG + bullish_sweep + near_support | bullish_sweep, near_support | 0 | 0.0 | 0.0 | 0.8439 | -3.5754 | 0.0 | 0 | 0 | NOISE |
| MAIN_SIGNAL LONG + HIGH_VOLATILITY | HIGH_VOLATILITY | 2 | 1.0 | 0.0 | 0.8368 | -3.5754 | 0.0 | 1 | 1 | NOISE |
| MAIN_SIGNAL LONG + RANGING | RANGING | 6 | 1.1689 | 0.5068 | 0.7949 | -4.0822 | -0.5068 | 3 | 3 | WATCH |
| MAIN_SIGNAL LONG + against_htf | against_htf | 9 | 1.1327 | 0.6636 | 0.7632 | -4.239 | -0.6636 | 4 | 5 | WATCH |
| MAIN_SIGNAL LONG + near_support | near_support | 9 | 1.127 | 0.762 | 0.7434 | -4.3374 | -0.762 | 3 | 6 | WATCH |
| MAIN_SIGNAL LONG + score_bucket 70-79 | score_bucket 70-79 | 1 | inf | 1.0 | 0.8002 | -4.5754 | -1.0 | 1 | 0 | NOISE |
| MAIN_SIGNAL LONG + body_ratio_below_threshold | body_ratio_below_threshold | 7 | 1.8879 | 2.6636 | 0.6865 | -6.239 | -2.6636 | 4 | 3 | WATCH |
| MAIN_SIGNAL LONG + distance_to_liquidity_penalty | distance_to_liquidity_penalty | 7 | 1.853 | 3.412 | 0.6304 | -6.9874 | -3.412 | 3 | 4 | WATCH |
| MAIN_SIGNAL LONG + BREAKOUT | BREAKOUT | 7 | 2.5851 | 4.7552 | 0.5815 | -8.3306 | -4.7552 | 4 | 3 | WATCH |
| MAIN_SIGNAL LONG + score_bucket 60-69 | score_bucket 60-69 | 5 | 3.456 | 4.912 | 0.594 | -8.4874 | -4.912 | 3 | 2 | WATCH |
| MAIN_SIGNAL LONG + timeframe_alignment_penalty | timeframe_alignment_penalty | 4 | 6.7552 | 5.7552 | 0.574 | -9.3306 | -5.7552 | 3 | 1 | NOISE |

## Answers

- toxicity_already_covered_by_existing_blocks: MAIN_SIGNAL_LONG is not net-negative in this dataset.
- remaining_toxicity_after_existing_blocks: trades=11, WR=45.4545%, PF=1.5698, TotalR=3.4188, AvgR=0.3108
- next_best_non_overlapping_root_cause: none
- globally_toxic: NO
- still_toxic_after_existing_blocks: NO
- block_redefine_or_keep: KEEP
- smallest_rule_least_collateral: none
- dominant_issue: liquidity_sweep
- best_single_root_cause: none
- best_multi_factor_root_cause: none
- best_survivor: liquidity_sweep=none (trades=14, PF=1.7027, TotalR=4.9188, class=NOISE)
- tiny_promising_survivor: rr_bucket=rr_1_5_to_2 (trades=6, PF=6.6636, TotalR=5.6636, class=NOISE)

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

### By Liquidity Sweep

| By Liquidity Sweep | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 | NOISE |

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

### By Failed Filter

| By Failed Filter | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
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

### By Condition Failed

| By Condition Failed | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| directional_confluence_failed | 4 | 1 | 3 | 25.0% | 0.3333 | -2.0 | -0.5 | WATCH |
| higher_timeframe_contradicts_long | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| market_structure_range_penalty | 7 | 4 | 3 | 57.1429% | 1.5023 | 1.5068 | 0.2153 | NOISE |
| body_ratio_below_threshold | 7 | 4 | 3 | 57.1429% | 1.8879 | 2.6636 | 0.3805 | NOISE |
| higher_timeframe_contradicts_short | 2 | 1 | 1 | 50.0% | 4.2552 | 3.2552 | 1.6276 | NOISE |
| distance_to_liquidity_penalty | 7 | 3 | 4 | 42.8571% | 1.853 | 3.412 | 0.4874 | NOISE |
| timeframe_alignment_penalty | 4 | 3 | 1 | 75.0% | 6.7552 | 5.7552 | 1.4388 | NOISE |

### By Volume Ratio Bucket

| By Volume Ratio Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| volume_low | 2 | 1 | 1 | 50.0% | 1.0 | 0.0 | 0.0 | NOISE |
| volume_mid | 2 | 1 | 1 | 50.0% | 1.5068 | 0.5068 | 0.2534 | NOISE |
| volume_high | 10 | 5 | 5 | 50.0% | 1.8824 | 4.412 | 0.4412 | NOISE |

### By Body Ratio Bucket

| By Body Ratio Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| UNKNOWN | 14 | 7 | 7 | 50.0% | 1.7027 | 4.9188 | 0.3513 | NOISE |

### By Distance To Liquidity Bucket

| By Distance To Liquidity Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| distance_close | 10 | 4 | 6 | 40.0% | 1.377 | 2.262 | 0.2262 | NOISE |
| distance_valid | 4 | 3 | 1 | 75.0% | 3.6568 | 2.6568 | 0.6642 | NOISE |

### By RR Bucket

| By RR Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| rr_2_plus | 8 | 2 | 6 | 25.0% | 0.8759 | -0.7448 | -0.0931 | WATCH |
| rr_1_5_to_2 | 6 | 5 | 1 | 83.3333% | 6.6636 | 5.6636 | 0.9439 | NOISE |

## Recommended Action

KEEP
