# WINNER_DNA_ANALYSIS

Generated at: 2026-06-09T15:52:13+00:00
Data path: data

## Executive Summary

- Baseline: trades=40, WR=32.5%, PF=0.8439, TotalR=-3.5754, AvgR=-0.0894
- Recommendation: Priorizar observación de trade_location=near_resistance. Tratar score_bucket=90+ como principal fuente de deterioro a investigar. La dimensión con mayor impacto medio es direction.

## Winner Profile

| Dimension | Value | Count | Share | Dataset Share | Overrepresentation |
|---|---|---:|---:|---:|---:|
| direction | long | 10 | 76.9231% | 47.5% | 29.4231 |
| rejection_reason | market_structure_range_penalty | 9 | 69.2308% | 57.5% | 11.7308 |
| session | LONDON | 6 | 46.1538% | 35.0% | 11.1538 |
| score_bucket | 60-69 | 5 | 38.4615% | 27.5% | 10.9615 |
| trade_location | near_resistance | 3 | 23.0769% | 12.5% | 10.5769 |
| liquidity_context | location:near_resistance | 3 | 23.0769% | 12.5% | 10.5769 |
| market_regime | RANGING | 7 | 53.8462% | 45.0% | 8.8462 |
| symbol | BNBUSDT | 3 | 23.0769% | 15.0% | 8.0769 |
| symbol | BTCUSDT | 2 | 15.3846% | 7.5% | 7.8846 |
| symbol | AVAXUSDT | 2 | 15.3846% | 7.5% | 7.8846 |
| setup_type | MAIN_SIGNAL | 8 | 61.5385% | 55.0% | 6.5385 |
| htf_alignment | against_htf | 7 | 53.8462% | 47.5% | 6.3462 |
| warning | against_htf | 7 | 53.8462% | 47.5% | 6.3462 |
| rejection_reason | body_ratio_below_threshold | 6 | 46.1538% | 40.0% | 6.1538 |
| rejection_reason | timeframe_alignment_penalty | 4 | 30.7692% | 25.0% | 5.7692 |
| symbol | DOTUSDT | 1 | 7.6923% | 2.5% | 5.1923 |
| symbol | INJUSDT | 1 | 7.6923% | 2.5% | 5.1923 |
| score_bucket | 70-79 | 1 | 7.6923% | 2.5% | 5.1923 |
| rejection_reason | higher_timeframe_contradicts_long | 1 | 7.6923% | 2.5% | 5.1923 |
| entry_context | BREAKOUT | 8 | 61.5385% | 57.5% | 4.0385 |
| trade_location | near_support | 5 | 38.4615% | 35.0% | 3.4615 |
| liquidity_context | location:near_support | 5 | 38.4615% | 35.0% | 3.4615 |
| trend_alignment | mixed_bullish_vs_bearish | 3 | 23.0769% | 20.0% | 3.0769 |
| score_bucket | 80-89 | 2 | 15.3846% | 12.5% | 2.8846 |
| warning | low_volume | 2 | 15.3846% | 12.5% | 2.8846 |
| trend_alignment | mixed_bearish_vs_bullish | 1 | 7.6923% | 5.0% | 2.6923 |
| rejection_reason | higher_timeframe_contradicts_short | 1 | 7.6923% | 5.0% | 2.6923 |
| trade_location | discount_zone | 2 | 15.3846% | 15.0% | 0.3846 |
| liquidity_context | location:discount_zone | 2 | 15.3846% | 15.0% | 0.3846 |
| warning | dirty_sideways_market | 2 | 15.3846% | 15.0% | 0.3846 |

## Loser Profile

| Dimension | Value | Count | Share | Dataset Share | Overrepresentation |
|---|---|---:|---:|---:|---:|
| direction | short | 18 | 66.6667% | 52.5% | 14.1667 |
| score_bucket | 90+ | 6 | 22.2222% | 15.0% | 7.2222 |
| rejection_reason | distance_to_liquidity_penalty | 16 | 59.2593% | 52.5% | 6.7593 |
| symbol | XRPUSDT | 4 | 14.8148% | 10.0% | 4.8148 |
| trade_location | premium_zone | 6 | 22.2222% | 17.5% | 4.7222 |
| liquidity_context | location:premium_zone | 6 | 22.2222% | 17.5% | 4.7222 |
| rejection_reason | directional_confluence_failed | 10 | 37.037% | 32.5% | 4.537 |
| session | NEW_YORK | 9 | 33.3333% | 30.0% | 3.3333 |
| setup_type | SECONDARY_SIGNAL | 13 | 48.1481% | 45.0% | 3.1481 |
| htf_alignment | aligned_with_htf | 15 | 55.5556% | 52.5% | 3.0556 |
| warning | explosive_candle_without_pullback | 2 | 7.4074% | 5.0% | 2.4074 |
| symbol | DOGEUSDT | 4 | 14.8148% | 12.5% | 2.3148 |
| market_regime | HIGH_VOLATILITY | 6 | 22.2222% | 20.0% | 2.2222 |
| trade_location | mid_range | 6 | 22.2222% | 20.0% | 2.2222 |
| liquidity_context | location:mid_range | 6 | 22.2222% | 20.0% | 2.2222 |
| market_regime | TRENDING | 10 | 37.037% | 35.0% | 2.037 |
| session | OVERLAP | 10 | 37.037% | 35.0% | 2.037 |
| trend_alignment | aligned_bullish | 10 | 37.037% | 35.0% | 2.037 |
| score_bucket | <60 | 12 | 44.4444% | 42.5% | 1.9444 |
| symbol | UNIUSDT | 1 | 3.7037% | 2.5% | 1.2037 |
| symbol | ETCUSDT | 1 | 3.7037% | 2.5% | 1.2037 |
| symbol | SANDUSDT | 1 | 3.7037% | 2.5% | 1.2037 |
| entry_context | CHOPPY_RANGE | 5 | 18.5185% | 17.5% | 1.0185 |
| entry_context | PULLBACK | 5 | 18.5185% | 17.5% | 1.0185 |
| rejection_reason | secondary_setup_requirements_failed | 5 | 18.5185% | 17.5% | 1.0185 |
| trend_alignment | aligned_bearish | 11 | 40.7407% | 40.0% | 0.7407 |
| entry_context | EXHAUSTION | 2 | 7.4074% | 7.5% | -0.0926 |
| trade_location | discount_zone | 4 | 14.8148% | 15.0% | -0.1852 |
| liquidity_context | location:discount_zone | 4 | 14.8148% | 15.0% | -0.1852 |
| warning | dirty_sideways_market | 4 | 14.8148% | 15.0% | -0.1852 |

## Top Positive Predictors

| Dimension | Value | Trades | WR | Uplift pp | PF | Total R | Avg R |
|---|---|---:|---:|---:|---:|---:|---:|
| trade_location | near_resistance | 5 | 60.0% | 27.5 | 2.5661 | 3.1323 | 0.6265 |
| liquidity_context | location:near_resistance | 5 | 60.0% | 27.5 | 2.5661 | 3.1323 | 0.6265 |
| direction | long | 19 | 52.6316% | 20.1316 | 1.7513 | 6.225 | 0.3276 |
| symbol | BNBUSDT | 6 | 50.0% | 17.5 | 1.1222 | 0.3667 | 0.0611 |
| score_bucket | 60-69 | 11 | 45.4545% | 12.9545 | 1.3267 | 1.96 | 0.1782 |
| session | LONDON | 14 | 42.8571% | 10.3571 | 1.5257 | 3.084 | 0.2203 |
| rejection_reason | timeframe_alignment_penalty | 10 | 40.0% | 7.5 | 1.3759 | 2.2552 | 0.2255 |
| score_bucket | 80-89 | 5 | 40.0% | 7.5 | 1.3749 | 0.5209 | 0.1042 |
| symbol | ETHUSDT | 5 | 40.0% | 7.5 | 1.0728 | 0.1586 | 0.0317 |
| rejection_reason | body_ratio_below_threshold | 16 | 37.5% | 5.0 | 1.0115 | 0.1146 | 0.0072 |
| htf_alignment | against_htf | 19 | 36.8421% | 4.3421 | 1.0493 | 0.4942 | 0.026 |
| warning | against_htf | 19 | 36.8421% | 4.3421 | 1.0493 | 0.4942 | 0.026 |
| setup_type | MAIN_SIGNAL | 22 | 36.3636% | 3.8636 | 1.0621 | 0.8698 | 0.0395 |
| trade_location | near_support | 14 | 35.7143% | 3.2143 | 1.064 | 0.5189 | 0.0371 |
| liquidity_context | location:near_support | 14 | 35.7143% | 3.2143 | 1.064 | 0.5189 | 0.0371 |
| entry_context | BREAKOUT | 23 | 34.7826% | 2.2826 | 1.0825 | 0.8996 | 0.0391 |

## Top Negative Predictors

| Dimension | Value | Trades | WR | Uplift pp | PF | Total R | Avg R |
|---|---|---:|---:|---:|---:|---:|---:|
| score_bucket | 90+ | 6 | 0.0% | -32.5 | 0.0 | -4.0366 | -0.6728 |
| direction | short | 21 | 14.2857% | -18.2143 | 0.3296 | -9.8004 | -0.4667 |
| trade_location | premium_zone | 7 | 14.2857% | -18.2143 | 0.0684 | -5.5896 | -0.7985 |
| liquidity_context | location:premium_zone | 7 | 14.2857% | -18.2143 | 0.0684 | -5.5896 | -0.7985 |
| symbol | DOGEUSDT | 5 | 20.0% | -12.5 | 0.468 | -1.1368 | -0.2274 |
| rejection_reason | directional_confluence_failed | 13 | 23.0769% | -9.4231 | 0.3876 | -4.5979 | -0.3537 |
| rejection_reason | distance_to_liquidity_penalty | 21 | 23.8095% | -8.6905 | 0.6098 | -5.4128 | -0.2578 |
| session | NEW_YORK | 12 | 25.0% | -7.5 | 0.288 | -6.4083 | -0.534 |
| trade_location | mid_range | 8 | 25.0% | -7.5 | 0.7022 | -1.3387 | -0.1673 |
| liquidity_context | location:mid_range | 8 | 25.0% | -7.5 | 0.7022 | -1.3387 | -0.1673 |
| market_regime | HIGH_VOLATILITY | 8 | 25.0% | -7.5 | 0.9802 | -0.0798 | -0.01 |
| setup_type | SECONDARY_SIGNAL | 18 | 27.7778% | -4.7222 | 0.5007 | -4.4452 | -0.247 |
| htf_alignment | aligned_with_htf | 21 | 28.5714% | -3.9286 | 0.6839 | -4.0696 | -0.1938 |
| entry_context | CHOPPY_RANGE | 7 | 28.5714% | -3.9286 | 0.2821 | -3.5896 | -0.5128 |
| trend_alignment | aligned_bullish | 14 | 28.5714% | -3.9286 | 0.7698 | -1.684 | -0.1203 |
| rejection_reason | secondary_setup_requirements_failed | 7 | 28.5714% | -3.9286 | 0.7616 | -0.5979 | -0.0854 |
| entry_context | PULLBACK | 7 | 28.5714% | -3.9286 | 0.8916 | -0.5422 | -0.0775 |
| session | OVERLAP | 14 | 28.5714% | -3.9286 | 0.9688 | -0.2511 | -0.0179 |
| score_bucket | <60 | 17 | 29.4118% | -3.0882 | 0.7369 | -3.0197 | -0.1776 |
| trend_alignment | aligned_bearish | 16 | 31.25% | -1.25 | 0.5675 | -4.1466 | -0.2592 |

## Counterfactual Uplift

| Dimension | Value | Removed | PF Before | PF After | TotalR Before | TotalR After | TotalR Uplift | WR Uplift |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| direction | short | 21 | 0.8439 | 1.7513 | -3.5754 | 6.225 | 9.8004 | 20.1316 |
| session | NEW_YORK | 12 | 0.8439 | 1.2038 | -3.5754 | 2.8329 | 6.4083 | 3.2143 |
| trade_location | premium_zone | 7 | 0.8439 | 1.1192 | -3.5754 | 2.0142 | 5.5896 | 3.8636 |
| liquidity_context | location:premium_zone | 7 | 0.8439 | 1.1192 | -3.5754 | 2.0142 | 5.5896 | 3.8636 |
| rejection_reason | distance_to_liquidity_penalty | 21 | 0.8439 | 1.2035 | -3.5754 | 1.8374 | 5.4128 | 9.6053 |
| rejection_reason | directional_confluence_failed | 13 | 0.8439 | 1.0664 | -3.5754 | 1.0225 | 4.5979 | 4.537 |
| setup_type | SECONDARY_SIGNAL | 18 | 0.8439 | 1.0621 | -3.5754 | 0.8698 | 4.4452 | 3.8636 |
| trend_alignment | aligned_bearish | 16 | 0.8439 | 1.0429 | -3.5754 | 0.5712 | 4.1466 | 0.8333 |
| htf_alignment | aligned_with_htf | 21 | 0.8439 | 1.0493 | -3.5754 | 0.4942 | 4.0696 | 4.3421 |
| score_bucket | 90+ | 6 | 0.8439 | 1.0244 | -3.5754 | 0.4612 | 4.0366 | 5.7353 |
| market_regime | RANGING | 18 | 0.8439 | 1.0352 | -3.5754 | 0.4369 | 4.0123 | -5.2273 |
| entry_context | CHOPPY_RANGE | 7 | 0.8439 | 1.0008 | -3.5754 | 0.0142 | 3.5896 | 0.8333 |
| score_bucket | <60 | 17 | 0.8439 | 0.9514 | -3.5754 | -0.5557 | 3.0197 | 2.2826 |
| warning | dirty_sideways_market | 6 | 0.8439 | 0.9479 | -3.5754 | -0.9858 | 2.5896 | -0.1471 |
| trend_alignment | aligned_bullish | 14 | 0.8439 | 0.8787 | -3.5754 | -1.8914 | 1.684 | 2.1154 |
| warning | low_volume | 5 | 0.8439 | 0.9002 | -3.5754 | -1.9858 | 1.5896 | -1.0714 |
| rejection_reason | market_structure_range_penalty | 23 | 0.8439 | 0.8075 | -3.5754 | -2.1246 | 1.4508 | -8.9706 |
| trade_location | mid_range | 8 | 0.8439 | 0.8785 | -3.5754 | -2.2367 | 1.3387 | 1.875 |
| liquidity_context | location:mid_range | 8 | 0.8439 | 0.8785 | -3.5754 | -2.2367 | 1.3387 | 1.875 |
| symbol | DOGEUSDT | 5 | 0.8439 | 0.8826 | -3.5754 | -2.4386 | 1.1368 | 1.7857 |
| trend_alignment | mixed_bullish_vs_bearish | 8 | 0.8439 | 0.8562 | -3.5754 | -2.5754 | 1.0 | -1.25 |
| rejection_reason | secondary_setup_requirements_failed | 7 | 0.8439 | 0.854 | -3.5754 | -2.9775 | 0.5979 | 0.8333 |
| entry_context | PULLBACK | 7 | 0.8439 | 0.8306 | -3.5754 | -3.0332 | 0.5422 | 0.8333 |
| trade_location | discount_zone | 6 | 0.8439 | 0.841 | -3.5754 | -3.2771 | 0.2983 | -0.1471 |
| liquidity_context | location:discount_zone | 6 | 0.8439 | 0.841 | -3.5754 | -3.2771 | 0.2983 | -0.1471 |
| session | OVERLAP | 14 | 0.8439 | 0.7764 | -3.5754 | -3.3243 | 0.2511 | 2.1154 |
| market_regime | HIGH_VOLATILITY | 8 | 0.8439 | 0.8148 | -3.5754 | -3.4956 | 0.0798 | 1.875 |
| rejection_reason | body_ratio_below_threshold | 16 | 0.8439 | 0.714 | -3.5754 | -3.69 | -0.1146 | -3.3333 |
| symbol | ETHUSDT | 5 | 0.8439 | 0.8198 | -3.5754 | -3.734 | -0.1586 | -1.0714 |
| symbol | BNBUSDT | 6 | 0.8439 | 0.8019 | -3.5754 | -3.9421 | -0.3667 | -3.0882 |

## Variable Impact Ranking

| Dimension | Groups | Covered Trades | Avg Abs WR Impact | Max Abs WR Impact |
|---|---:|---:|---:|---:|
| direction | 2 | 40 | 19.173 | 20.1316 |
| score_bucket | 4 | 39 | 14.0107 | 32.5 |
| symbol | 3 | 16 | 12.5 | 17.5 |
| trade_location | 5 | 40 | 11.4524 | 27.5 |
| liquidity_context | 5 | 40 | 11.4524 | 27.5 |
| session | 3 | 40 | 7.2619 | 10.3571 |
| rejection_reason | 6 | 90 | 6.8621 | 9.4231 |
| market_regime | 3 | 40 | 5.9392 | 7.5 |
| setup_type | 2 | 40 | 4.2929 | 4.7222 |
| warning | 3 | 30 | 4.2251 | 7.5 |
| htf_alignment | 2 | 40 | 4.1354 | 4.3421 |
| trend_alignment | 3 | 38 | 3.3929 | 5.0 |
| entry_context | 3 | 37 | 3.3799 | 3.9286 |

## Final Recommendation

Variables con mayor probabilidad incremental de éxito:
- trade_location=near_resistance (WR 60.0%, uplift 27.5 pp, PF 2.5661, TotalR 3.1323)
- liquidity_context=location:near_resistance (WR 60.0%, uplift 27.5 pp, PF 2.5661, TotalR 3.1323)
- direction=long (WR 52.6316%, uplift 20.1316 pp, PF 1.7513, TotalR 6.225)
- symbol=BNBUSDT (WR 50.0%, uplift 17.5 pp, PF 1.1222, TotalR 0.3667)
- score_bucket=60-69 (WR 45.4545%, uplift 12.9545 pp, PF 1.3267, TotalR 1.96)

Variables que más reducen probabilidad de éxito:
- score_bucket=90+ (WR 0.0%, uplift -32.5 pp, PF 0.0, TotalR -4.0366)
- direction=short (WR 14.2857%, uplift -18.2143 pp, PF 0.3296, TotalR -9.8004)
- trade_location=premium_zone (WR 14.2857%, uplift -18.2143 pp, PF 0.0684, TotalR -5.5896)
- liquidity_context=location:premium_zone (WR 14.2857%, uplift -18.2143 pp, PF 0.0684, TotalR -5.5896)
- symbol=DOGEUSDT (WR 20.0%, uplift -12.5 pp, PF 0.468, TotalR -1.1368)
