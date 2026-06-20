# POST_BULLISH_SWEEP_COUNTERFACTUAL_ANALYSIS

Generated at: 2026-06-05T15:56:18+00:00
Data path: data
Method: removed all trades where `liquidity_context=sweep:bullish_sweep` or `liquidity_sweep=bullish_sweep`.

## Executive Summary

- Current system: trades=40, WR=32.5%, PF=0.8439, TotalR=-3.5754, AvgR=-0.0894
- Removed bullish_sweep only: trades=0, WR=0.0%, PF=0.0, TotalR=0.0, AvgR=0.0
- System without bullish_sweep: trades=40, WR=32.5%, PF=0.8439, TotalR=-3.5754, AvgR=-0.0894
- Is system profitable after removing bullish_sweep? NO
- Largest loss contributor: session=NEW_YORK (trades=12, PF=0.288, TotalR=-6.4083, class=IMPORTANT)
- Second largest loss contributor: liquidity_context=location:premium_zone (trades=7, PF=0.0684, TotalR=-5.5896, class=WATCH)
- Third largest loss contributor: rejection_reason=distance_to_liquidity_penalty (trades=21, PF=0.6098, TotalR=-5.4128, class=CRITICAL)
- Remaining component with enough sample size: session=NEW_YORK (trades=12, PF=0.288, TotalR=-6.4083, class=IMPORTANT)
- Probably noise: short_subset=SHORT|MAIN_SIGNAL|NEW_YORK|RANGING|CHOPPY_RANGE|premium_zone (trades=2, PF=0.0, TotalR=-2.0, class=NOISE)

## New Enemy Ranking

| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| session | NEW_YORK | 12 | 3 | 9 | 25.0% | 0.288 | -6.4083 | -0.534 | IMPORTANT |
| liquidity_context | location:premium_zone | 7 | 1 | 6 | 14.29% | 0.0684 | -5.5896 | -0.7985 | WATCH |
| rejection_reason | distance_to_liquidity_penalty | 21 | 5 | 16 | 23.81% | 0.6098 | -5.4128 | -0.2578 | CRITICAL |
| rejection_reason | directional_confluence_failed | 13 | 3 | 10 | 23.08% | 0.3876 | -4.5979 | -0.3537 | IMPORTANT |
| setup_type | SECONDARY_SIGNAL | 18 | 5 | 13 | 27.78% | 0.5007 | -4.4452 | -0.247 | IMPORTANT |
| trend_alignment | aligned_bearish | 16 | 5 | 11 | 31.25% | 0.5675 | -4.1466 | -0.2592 | IMPORTANT |
| score_bucket | 90+ | 6 | 0 | 6 | 0.0% | 0.0 | -4.0366 | -0.6728 | WATCH |
| market_regime | RANGING | 18 | 7 | 11 | 38.89% | 0.6171 | -4.0123 | -0.2229 | IMPORTANT |
| penalty | none | 40 | 13 | 27 | 32.5% | 0.8439 | -3.5754 | -0.0894 | IMPORTANT |
| score_bucket | <60 | 17 | 5 | 12 | 29.41% | 0.7369 | -3.0197 | -0.1776 | IMPORTANT |
| warning | dirty_sideways_market | 6 | 2 | 4 | 33.33% | 0.3526 | -2.5896 | -0.4316 | WATCH |
| symbol | XRPUSDT | 4 | 0 | 4 | 0.0% | 0.0 | -2.5873 | -0.6468 | WATCH |
| warning | none | 16 | 5 | 11 | 31.25% | 0.7914 | -2.0563 | -0.1285 | IMPORTANT |
| short_subset | SHORT|MAIN_SIGNAL|NEW_YORK|RANGING|CHOPPY_RANGE|premium_zone | 2 | 0 | 2 | 0.0% | 0.0 | -2.0 | -1.0 | NOISE |
| short_subset | SHORT|MAIN_SIGNAL|NEW_YORK|TRENDING|PULLBACK|premium_zone | 2 | 0 | 2 | 0.0% | 0.0 | -2.0 | -1.0 | NOISE |
| symbol | SOLUSDT | 4 | 1 | 3 | 25.0% | 0.3333 | -2.0 | -0.5 | WATCH |
| trend_alignment | aligned_bullish | 14 | 4 | 10 | 28.57% | 0.7698 | -1.684 | -0.1203 | IMPORTANT |
| warning | low_volume | 5 | 2 | 3 | 40.0% | 0.4701 | -1.5896 | -0.3179 | WATCH |
| short_subset | SHORT|SECONDARY_SIGNAL|LONDON|RANGING|BREAKOUT|discount_zone | 2 | 0 | 2 | 0.0% | 0.0 | -1.4775 | -0.7388 | NOISE |
| rejection_reason | market_structure_range_penalty | 23 | 9 | 14 | 39.13% | 0.8777 | -1.4508 | -0.0631 | IMPORTANT |
| liquidity_context | location:mid_range | 8 | 2 | 6 | 25.0% | 0.7022 | -1.3387 | -0.1673 | WATCH |
| short_subset | SHORT|SECONDARY_SIGNAL|LONDON|HIGH_VOLATILITY|BREAKOUT|mid_range | 2 | 0 | 2 | 0.0% | 0.0 | -1.21 | -0.605 | NOISE |
| symbol | DOGEUSDT | 5 | 1 | 4 | 20.0% | 0.468 | -1.1368 | -0.2274 | WATCH |
| short_subset | SHORT|SECONDARY_SIGNAL|OVERLAP|TRENDING|BREAKOUT|near_support | 2 | 0 | 2 | 0.0% | 0.0 | -1.1098 | -0.5549 | NOISE |
| warning | explosive_candle_without_pullback | 2 | 0 | 2 | 0.0% | 0.0 | -1.0133 | -0.5067 | NOISE |
| symbol | APEUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| symbol | ATOMUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| symbol | ETCUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| symbol | ICPUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| symbol | SANDUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |

## Worst Symbols

| Symbol | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| XRPUSDT | 4 | 0 | 4 | 0.0% | 0.0 | -2.5873 | -0.6468 | WATCH |
| SOLUSDT | 4 | 1 | 3 | 25.0% | 0.3333 | -2.0 | -0.5 | WATCH |
| DOGEUSDT | 5 | 1 | 4 | 20.0% | 0.468 | -1.1368 | -0.2274 | WATCH |
| APEUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ATOMUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ETCUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ICPUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SANDUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SUIUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| TRXUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| UNIUSDT | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| ETHUSDT | 5 | 2 | 3 | 40.0% | 1.0728 | 0.1586 | 0.0317 | NOISE |
| BNBUSDT | 6 | 3 | 3 | 50.0% | 1.1222 | 0.3667 | 0.0611 | NOISE |
| AVAXUSDT | 3 | 2 | 1 | 66.67% | 1.9172 | 0.9172 | 0.3057 | NOISE |
| DOTUSDT | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |
| INJUSDT | 1 | 1 | 0 | 100.0% | inf | 2.951 | 2.951 | NOISE |
| BTCUSDT | 3 | 2 | 1 | 66.67% | 5.2552 | 4.2552 | 1.4184 | NOISE |

## Worst Sessions

| Session | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| NEW_YORK | 12 | 3 | 9 | 25.0% | 0.288 | -6.4083 | -0.534 | IMPORTANT |
| OVERLAP | 14 | 4 | 10 | 28.57% | 0.9688 | -0.2511 | -0.0179 | IMPORTANT |
| LONDON | 14 | 6 | 8 | 42.86% | 1.5257 | 3.084 | 0.2203 | NOISE |

## Worst Market Regimes

| Market Regime | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| RANGING | 18 | 7 | 11 | 38.89% | 0.6171 | -4.0123 | -0.2229 | IMPORTANT |
| HIGH_VOLATILITY | 8 | 2 | 6 | 25.0% | 0.9802 | -0.0798 | -0.01 | WATCH |
| TRENDING | 14 | 4 | 10 | 28.57% | 1.0615 | 0.5167 | 0.0369 | NOISE |

## Worst Setup Types

| Setup Type | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SECONDARY_SIGNAL | 18 | 5 | 13 | 27.78% | 0.5007 | -4.4452 | -0.247 | IMPORTANT |
| MAIN_SIGNAL | 22 | 8 | 14 | 36.36% | 1.0621 | 0.8698 | 0.0395 | NOISE |

## Worst Score Buckets

| Score Bucket | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 90+ | 6 | 0 | 6 | 0.0% | 0.0 | -4.0366 | -0.6728 | WATCH |
| <60 | 17 | 5 | 12 | 29.41% | 0.7369 | -3.0197 | -0.1776 | IMPORTANT |
| 80-89 | 5 | 2 | 3 | 40.0% | 1.3749 | 0.5209 | 0.1042 | NOISE |
| 70-79 | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| 60-69 | 11 | 5 | 6 | 45.45% | 1.3267 | 1.96 | 0.1782 | NOISE |

## Worst Warnings

| Warning | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| dirty_sideways_market | 6 | 2 | 4 | 33.33% | 0.3526 | -2.5896 | -0.4316 | WATCH |
| none | 16 | 5 | 11 | 31.25% | 0.7914 | -2.0563 | -0.1285 | IMPORTANT |
| low_volume | 5 | 2 | 3 | 40.0% | 0.4701 | -1.5896 | -0.3179 | WATCH |
| explosive_candle_without_pullback | 2 | 0 | 2 | 0.0% | 0.0 | -1.0133 | -0.5067 | NOISE |
| against_htf | 19 | 7 | 12 | 36.84% | 1.0493 | 0.4942 | 0.026 | NOISE |

## Worst Penalties

| Penalty | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 40 | 13 | 27 | 32.5% | 0.8439 | -3.5754 | -0.0894 | IMPORTANT |

## Worst Rejection Reasons

| Rejection Reason | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| distance_to_liquidity_penalty | 21 | 5 | 16 | 23.81% | 0.6098 | -5.4128 | -0.2578 | CRITICAL |
| directional_confluence_failed | 13 | 3 | 10 | 23.08% | 0.3876 | -4.5979 | -0.3537 | IMPORTANT |
| market_structure_range_penalty | 23 | 9 | 14 | 39.13% | 0.8777 | -1.4508 | -0.0631 | IMPORTANT |
| secondary_setup_requirements_failed | 7 | 2 | 5 | 28.57% | 0.7616 | -0.5979 | -0.0854 | WATCH |
| body_ratio_below_threshold | 16 | 6 | 10 | 37.5% | 1.0115 | 0.1146 | 0.0072 | NOISE |
| higher_timeframe_contradicts_long | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| timeframe_alignment_penalty | 10 | 4 | 6 | 40.0% | 1.3759 | 2.2552 | 0.2255 | NOISE |
| higher_timeframe_contradicts_short | 2 | 1 | 1 | 50.0% | 4.2552 | 3.2552 | 1.6276 | NOISE |

## Worst Liquidity Contexts Excluding Bullish Sweep

| Liquidity Context | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| location:premium_zone | 7 | 1 | 6 | 14.29% | 0.0684 | -5.5896 | -0.7985 | WATCH |
| location:mid_range | 8 | 2 | 6 | 25.0% | 0.7022 | -1.3387 | -0.1673 | WATCH |
| location:discount_zone | 6 | 2 | 4 | 33.33% | 0.8702 | -0.2983 | -0.0497 | WATCH |
| location:near_support | 14 | 5 | 9 | 35.71% | 1.064 | 0.5189 | 0.0371 | NOISE |
| location:near_resistance | 5 | 3 | 2 | 60.0% | 2.5661 | 3.1323 | 0.6265 | NOISE |

## Worst Trend Alignment Groups

| Trend Alignment | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| aligned_bearish | 16 | 5 | 11 | 31.25% | 0.5675 | -4.1466 | -0.2592 | IMPORTANT |
| aligned_bullish | 14 | 4 | 10 | 28.57% | 0.7698 | -1.684 | -0.1203 | IMPORTANT |
| mixed_bullish_vs_bearish | 8 | 3 | 5 | 37.5% | 0.8 | -1.0 | -0.125 | WATCH |
| mixed_bearish_vs_bullish | 2 | 1 | 1 | 50.0% | 4.2552 | 3.2552 | 1.6276 | NOISE |

## Worst LONG Subsets

| LONG Subset | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| LONG|MAIN_SIGNAL|NEW_YORK|HIGH_VOLATILITY|BREAKOUT|near_support | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| LONG|MAIN_SIGNAL|OVERLAP|RANGING|BREAKOUT|near_support | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| LONG|MAIN_SIGNAL|OVERLAP|RANGING|PULLBACK|mid_range | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| LONG|MAIN_SIGNAL|OVERLAP|TRENDING|EXHAUSTION|near_support | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| LONG|MAIN_SIGNAL|OVERLAP|TRENDING|PULLBACK|near_support | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| LONG|SECONDARY_SIGNAL|OVERLAP|HIGH_VOLATILITY|BREAKOUT|premium_zone | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| LONG|SECONDARY_SIGNAL|OVERLAP|TRENDING|BREAKOUT|mid_range | 1 | 0 | 1 | 0.0% | 0.0 | -0.2855 | -0.2855 | NOISE |
| LONG|MAIN_SIGNAL|LONDON|RANGING|CHOPPY_RANGE|near_support | 2 | 1 | 1 | 50.0% | 1.0 | 0.0 | 0.0 | NOISE |
| LONG|SECONDARY_SIGNAL|NEW_YORK|RANGING|CHOPPY_RANGE|premium_zone | 1 | 1 | 0 | 100.0% | inf | 0.4104 | 0.4104 | NOISE |
| LONG|SECONDARY_SIGNAL|NEW_YORK|RANGING|BREAKOUT|near_resistance | 1 | 1 | 0 | 100.0% | inf | 0.6813 | 0.6813 | NOISE |
| LONG|MAIN_SIGNAL|LONDON|HIGH_VOLATILITY|BREAKOUT|discount_zone | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| LONG|MAIN_SIGNAL|LONDON|RANGING|BREAKOUT|discount_zone | 1 | 1 | 0 | 100.0% | inf | 1.0 | 1.0 | NOISE |
| LONG|MAIN_SIGNAL|LONDON|TRENDING|BREAKOUT|near_resistance | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |
| LONG|SECONDARY_SIGNAL|NEW_YORK|TRENDING|BREAKOUT|mid_range | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |
| LONG|MAIN_SIGNAL|OVERLAP|RANGING|PULLBACK|near_support | 1 | 1 | 0 | 100.0% | inf | 1.5068 | 1.5068 | NOISE |
| LONG|MAIN_SIGNAL|OVERLAP|TRENDING|EXHAUSTION|mid_range | 1 | 1 | 0 | 100.0% | inf | 1.6568 | 1.6568 | NOISE |
| LONG|MAIN_SIGNAL|OVERLAP|TRENDING|BREAKOUT|near_support | 2 | 1 | 1 | 50.0% | 4.2552 | 3.2552 | 1.6276 | NOISE |

## Worst SHORT Subsets

| SHORT Subset | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SHORT|MAIN_SIGNAL|NEW_YORK|RANGING|CHOPPY_RANGE|premium_zone | 2 | 0 | 2 | 0.0% | 0.0 | -2.0 | -1.0 | NOISE |
| SHORT|MAIN_SIGNAL|NEW_YORK|TRENDING|PULLBACK|premium_zone | 2 | 0 | 2 | 0.0% | 0.0 | -2.0 | -1.0 | NOISE |
| SHORT|SECONDARY_SIGNAL|LONDON|RANGING|BREAKOUT|discount_zone | 2 | 0 | 2 | 0.0% | 0.0 | -1.4775 | -0.7388 | NOISE |
| SHORT|SECONDARY_SIGNAL|LONDON|HIGH_VOLATILITY|BREAKOUT|mid_range | 2 | 0 | 2 | 0.0% | 0.0 | -1.21 | -0.605 | NOISE |
| SHORT|SECONDARY_SIGNAL|OVERLAP|TRENDING|BREAKOUT|near_support | 2 | 0 | 2 | 0.0% | 0.0 | -1.1098 | -0.5549 | NOISE |
| SHORT|MAIN_SIGNAL|LONDON|RANGING|CHOPPY_RANGE|near_resistance | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SHORT|MAIN_SIGNAL|LONDON|TRENDING|PULLBACK|near_resistance | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SHORT|MAIN_SIGNAL|NEW_YORK|RANGING|EXHAUSTION|premium_zone | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SHORT|SECONDARY_SIGNAL|NEW_YORK|RANGING|BREAKOUT|near_support | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SHORT|SECONDARY_SIGNAL|NEW_YORK|RANGING|CHOPPY_RANGE|mid_range | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SHORT|SECONDARY_SIGNAL|NEW_YORK|TRENDING|BREAKOUT|mid_range | 1 | 0 | 1 | 0.0% | 0.0 | -1.0 | -1.0 | NOISE |
| SHORT|SECONDARY_SIGNAL|OVERLAP|HIGH_VOLATILITY|BREAKOUT|discount_zone | 1 | 0 | 1 | 0.0% | 0.0 | -0.6413 | -0.6413 | NOISE |
| SHORT|SECONDARY_SIGNAL|LONDON|HIGH_VOLATILITY|BREAKOUT|discount_zone | 1 | 0 | 1 | 0.0% | 0.0 | -0.1795 | -0.1795 | NOISE |
| SHORT|SECONDARY_SIGNAL|OVERLAP|RANGING|BREAKOUT|near_support | 1 | 1 | 0 | 100.0% | inf | 0.3667 | 0.3667 | NOISE |
| SHORT|SECONDARY_SIGNAL|LONDON|RANGING|BREAKOUT|near_support | 1 | 1 | 0 | 100.0% | inf | 1.5 | 1.5 | NOISE |
| SHORT|MAIN_SIGNAL|LONDON|HIGH_VOLATILITY|PULLBACK|near_resistance | 1 | 1 | 0 | 100.0% | inf | 2.951 | 2.951 | NOISE |

## Next Investigation Recommendation

Deep dive `session=NEW_YORK`.
