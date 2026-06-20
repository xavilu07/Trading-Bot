# DISTANCE_TO_LIQUIDITY_ROOT_CAUSE_ANALYSIS

Generated at: 2026-06-09T18:01:21+00:00
Data path: data
Method: Analyze canonical closed trades tagged with distance_to_liquidity_penalty, including counterfactual removal before and after already-blocked bullish_sweep and against_htf+BREAKOUT contexts.
Classification: IMPORTANT
Recommended action: REDEFINE_ENTRY

## Executive Summary

- Baseline: trades=40, WR=32.5%, PF=0.8439, TotalR=-3.5754, AvgR=-0.0894
- distance_to_liquidity_penalty: trades=21, WR=23.8095%, PF=0.6098, TotalR=-5.4128, AvgR=-0.2578
- After existing blocks: trades=19, WR=21.0526%, PF=0.5407, TotalR=-5.9128, AvgR=-0.3112
- Is liquidity distance itself toxic? YES
- Toxicity remains after existing blocks? YES
- Root cause or correlated? mixed_signal_symptom_requires_entry_redefinition
- Blocking improves PF? YES
- Partial better than full block? YES

## Baseline

| Trades | Wins | Losses | WR | PF | Total R | Avg R |
|---:|---:|---:|---:|---:|---:|---:|
| 21 | 5 | 16 | 23.8095% | 0.6098 | -5.4128 | -0.2578 |

## Breakdowns

### By Symbol

| By Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SOLUSDT | 3 | 0 | 3 | 0.0% | 0.0 | -3.0 | -1.0 | WATCH |
| XRPUSDT | 4 | 0 | 4 | 0.0% | 0.0 | -2.5873 | -0.6468 | WATCH |
| AVAXUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ICPUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SANDUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| TRXUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| DOGEUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -0.2855 | -0.2855 | NOISE |
| ETHUSDT | 4 | 2 | 2 | 50.0% | 1.169 | 0.3381 | 0.0845 | NOISE |
| BNBUSDT | 3 | 2 | 1 | 66.6667% | 1.8667 | 0.8667 | 0.2889 | NOISE |
| BTCUSDT | 2 | 1 | 1 | 50.0% | 4.2552 | 3.2552 | 1.6276 | NOISE |

### By Session

| By Session | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| NEW_YORK | 5 | 1 | 4 | 20.0% | 0.1703 | -3.3187 | -0.6637 | WATCH |
| LONDON | 6 | 1 | 5 | 16.6667% | 0.335 | -2.9775 | -0.4963 | WATCH |
| OVERLAP | 10 | 3 | 7 | 30.0% | 1.1637 | 0.8834 | 0.0883 | NOISE |

### By Market Regime

| By Market Regime | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| RANGING | 9 | 2 | 7 | 22.2222% | 0.1618 | -5.4295 | -0.6033 | WATCH |
| HIGH_VOLATILITY | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| TRENDING | 11 | 3 | 8 | 27.2727% | 1.159 | 1.0167 | 0.0924 | NOISE |

### By Direction

| By Direction | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| short | 11 | 1 | 10 | 9.0909% | 0.0427 | -8.2206 | -0.7473 | IMPORTANT |
| long | 10 | 4 | 6 | 40.0% | 1.5312 | 2.8078 | 0.2808 | NOISE |

### By Setup Type

| By Setup Type | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SECONDARY_SIGNAL | 9 | 2 | 7 | 22.2222% | 0.2151 | -3.8248 | -0.425 | WATCH |
| MAIN_SIGNAL | 12 | 3 | 9 | 25.0% | 0.8236 | -1.588 | -0.1323 | IMPORTANT |

### By Score Bucket

| By Score Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| <60 | 9 | 1 | 8 | 11.1111% | 0.2006 | -5.9775 | -0.6642 | WATCH |
| 90+ | 3 | 0 | 3 | 0.0% | 0.0 | -1.3953 | -0.4651 | WATCH |
| 60-69 | 9 | 4 | 5 | 44.4444% | 1.392 | 1.96 | 0.2178 | NOISE |

### By Liquidity Sweep

| By Liquidity Sweep | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 21 | 5 | 16 | 23.8095% | 0.6098 | -5.4128 | -0.2578 | IMPORTANT |

### By Trade Location

| By Trade Location | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| premium_zone | 4 | 0 | 4 | 0.0% | 0.0 | -4.0 | -1.0 | WATCH |
| near_support | 9 | 2 | 7 | 22.2222% | 0.7565 | -1.4879 | -0.1653 | WATCH |
| discount_zone | 2 | 0 | 2 | 0.0% | 0.0 | -1.4775 | -0.7388 | NOISE |
| near_resistance | 4 | 2 | 2 | 50.0% | 1.0907 | 0.1813 | 0.0453 | NOISE |
| mid_range | 2 | 1 | 1 | 50.0% | 5.8032 | 1.3713 | 0.6857 | NOISE |

### By Trend Alignment

| By Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_bearish | 10 | 2 | 8 | 20.0% | 0.3072 | -4.5638 | -0.4564 | IMPORTANT |
| aligned_bullish | 5 | 1 | 4 | 20.0% | 0.2074 | -2.6042 | -0.5208 | WATCH |
| mixed_bullish_vs_bearish | 4 | 1 | 3 | 25.0% | 0.5 | -1.5 | -0.375 | WATCH |
| mixed_bearish_vs_bullish | 2 | 1 | 1 | 50.0% | 4.2552 | 3.2552 | 1.6276 | NOISE |

### By HTF Alignment

| By HTF Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_with_htf | 14 | 3 | 11 | 21.4286% | 0.5977 | -3.5696 | -0.255 | IMPORTANT |
| against_htf | 7 | 2 | 5 | 28.5714% | 0.6314 | -1.8432 | -0.2633 | WATCH |

## Toxic Combinations

Tested fixed combinations requested for distance_to_liquidity_penalty.

| Rule | Removed | Removed PF | Removed TotalR | PF After | TotalR After | PF Improvement | R Improvement | Profitable Lost | Losing Removed | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| distance_to_liquidity_penalty + RANGING | 9 | 0.1618 | -5.4295 | 1.1129 | 1.8541 | 0.269 | 5.4295 | 2 | 7 | WATCH |
| distance_to_liquidity_penalty + NEW_YORK | 5 | 0.1703 | -3.3187 | 0.9864 | -0.2567 | 0.1425 | 3.3187 | 1 | 4 | WATCH |
| distance_to_liquidity_penalty + against_htf | 7 | 0.6314 | -1.8432 | 0.9032 | -1.7322 | 0.0593 | 1.8432 | 2 | 5 | WATCH |
| distance_to_liquidity_penalty + MAIN_SIGNAL | 12 | 0.8236 | -1.588 | 0.8571 | -1.9874 | 0.0132 | 1.588 | 3 | 9 | IMPORTANT |
| distance_to_liquidity_penalty + HIGH_VOLATILITY | 1 | 0.0 | -1.0 | 0.8824 | -2.5754 | 0.0385 | 1.0 | 0 | 1 | NOISE |
| distance_to_liquidity_penalty + bullish_sweep | 0 | 0.0 | 0.0 | 0.8439 | -3.5754 | 0.0 | 0.0 | 0 | 0 | NOISE |
| distance_to_liquidity_penalty + OVERLAP | 10 | 1.1637 | 0.8834 | 0.7453 | -4.4588 | -0.0986 | -0.8834 | 3 | 7 | WATCH |
| distance_to_liquidity_penalty + LONG | 10 | 1.5312 | 2.8078 | 0.6377 | -6.3832 | -0.2062 | -2.8078 | 4 | 6 | WATCH |

## Survivors

Criteria: minimum 10 trades, PF > 1.1, TotalR > 0.

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| direction | long | 10 | 4 | 6 | 40.0% | 1.5312 | 2.8078 | 0.2808 | NOISE |
| market_regime | TRENDING | 11 | 3 | 8 | 27.2727% | 1.159 | 1.0167 | 0.0924 | NOISE |
| session | OVERLAP | 10 | 3 | 7 | 30.0% | 1.1637 | 0.8834 | 0.0883 | NOISE |

## Toxic Subgroups

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| direction | short | 11 | 1 | 10 | 9.0909% | 0.0427 | -8.2206 | -0.7473 | IMPORTANT |
| liquidity_sweep | none | 21 | 5 | 16 | 23.8095% | 0.6098 | -5.4128 | -0.2578 | IMPORTANT |
| trend_alignment | aligned_bearish | 10 | 2 | 8 | 20.0% | 0.3072 | -4.5638 | -0.4564 | IMPORTANT |
| htf_alignment | aligned_with_htf | 14 | 3 | 11 | 21.4286% | 0.5977 | -3.5696 | -0.255 | IMPORTANT |
| setup_type | MAIN_SIGNAL | 12 | 3 | 9 | 25.0% | 0.8236 | -1.588 | -0.1323 | IMPORTANT |

## Counterfactuals

| Scenario | Removed | PF Before | PF After | TotalR Before | TotalR After | PF Improvement | R Improvement | WR Delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| without_distance_to_liquidity_penalty | 21 | 0.8439 | 1.2035 | -3.5754 | 1.8374 | 0.3596 | 5.4128 | 9.6053 |
| without_existing_production_blocks | 8 | 0.8439 | 0.7713 | -3.5754 | -4.5446 | -0.0726 | -0.9692 | -1.25 |
| without_distance_to_liquidity_penalty_after_existing_blocks | 19 | 0.7713 | 1.1955 | -4.5446 | 1.3682 | 0.4242 | 5.9128 | 14.9038 |

## Answers

- liquidity_distance_itself_toxic: YES
- toxicity_remains_after_existing_blocks: YES
- root_cause_or_correlated: mixed_signal_symptom_requires_entry_redefinition
- blocking_improves_pf: YES
- blocking_improves_pf_after_existing_blocks: YES
- partial_rule_better_than_full_block: YES
- best_partial_rule: distance_to_liquidity_penalty + MAIN_SIGNAL (removed=12, PF=0.8236, TotalR=-1.588, R improvement=1.588, class=IMPORTANT)
- best_survivor: direction=long (trades=10, PF=1.5312, TotalR=2.8078, class=NOISE)

## Recommended Action

REDEFINE_ENTRY
