# Overview

- trades: 49
- closed: 49
- open: 0
- wins: 18
- losses: 28
- neutral: 3
- winrate: 36.7347
- profit_factor: 0.9125
- total_r: -2.0783
- avg_r: -0.0424
- median_r: -0.382
- expectancy: -0.0424
- average_win: 1.204
- average_loss: -0.8482
- std_dev: 1.1602
- drawdown: -7.918
- evidence: 49
- confidence: MEDIUM

## Condition Debug
- total_candidate_conditions_before_filter: 121
- total_candidate_conditions_after_filter: 30
- skipped_constant_features: [{'feature': 'strategy', 'values': 1, 'dominant_value': 'liquidity_sweep_mtf_v1', 'dominant_count': 49, 'closed_count': 49}, {'feature': 'paper_level', 'values': 1, 'dominant_value': 'HIGH', 'dominant_count': 49, 'closed_count': 49}, {'feature': 'rr_valid', 'values': 1, 'dominant_value': 'True', 'dominant_count': 49, 'closed_count': 49}, {'feature': 'late_entry_from_bos', 'values': 1, 'dominant_value': 'False', 'dominant_count': 49, 'closed_count': 49}]
- skipped_low_evidence: [{'feature': 'symbol', 'operator': '==', 'value': 'BNBUSDT', 'evidence': 6}, {'feature': 'symbol', 'operator': '==', 'value': 'BTCUSDT', 'evidence': 5}, {'feature': 'symbol', 'operator': '==', 'value': 'ETHUSDT', 'evidence': 5}, {'feature': 'symbol', 'operator': '==', 'value': 'XRPUSDT', 'evidence': 5}, {'feature': 'symbol', 'operator': '==', 'value': 'DOGEUSDT', 'evidence': 5}, {'feature': 'symbol', 'operator': '==', 'value': 'SOLUSDT', 'evidence': 4}, {'feature': 'symbol', 'operator': '==', 'value': 'AVAXUSDT', 'evidence': 3}, {'feature': 'symbol', 'operator': '==', 'value': 'MANAUSDT', 'evidence': 2}, {'feature': 'session', 'operator': '==', 'value': 'LONDON', 'evidence': 18}, {'feature': 'session', 'operator': '==', 'value': 'NEW_YORK', 'evidence': 16}, {'feature': 'session', 'operator': '==', 'value': 'OVERLAP', 'evidence': 14}, {'feature': 'session', 'operator': '==', 'value': 'ASIA', 'evidence': 1}, {'feature': 'utc_hour', 'operator': '==', 'value': '21', 'evidence': 10}, {'feature': 'utc_hour', 'operator': '==', 'value': '14', 'evidence': 8}, {'feature': 'utc_hour', 'operator': '==', 'value': '15', 'evidence': 5}, {'feature': 'utc_hour', 'operator': '==', 'value': '22', 'evidence': 5}, {'feature': 'utc_hour', 'operator': '==', 'value': '13', 'evidence': 4}, {'feature': 'utc_hour', 'operator': '==', 'value': '12', 'evidence': 4}, {'feature': 'utc_hour', 'operator': '==', 'value': '11', 'evidence': 4}, {'feature': 'utc_hour', 'operator': '==', 'value': '10', 'evidence': 3}, {'feature': 'opened_weekday', 'operator': '==', 'value': 'Sunday', 'evidence': 17}, {'feature': 'opened_weekday', 'operator': '==', 'value': 'Tuesday', 'evidence': 13}, {'feature': 'opened_weekday', 'operator': '==', 'value': 'Monday', 'evidence': 11}, {'feature': 'opened_weekday', 'operator': '==', 'value': 'Wednesday', 'evidence': 5}, {'feature': 'opened_weekday', 'operator': '==', 'value': 'Saturday', 'evidence': 2}, {'feature': 'opened_weekday', 'operator': '==', 'value': 'Friday', 'evidence': 1}, {'feature': 'opened_hour_utc', 'operator': '==', 'value': '21', 'evidence': 10}, {'feature': 'opened_hour_utc', 'operator': '==', 'value': '14', 'evidence': 8}, {'feature': 'opened_hour_utc', 'operator': '==', 'value': '15', 'evidence': 5}, {'feature': 'opened_hour_utc', 'operator': '==', 'value': '22', 'evidence': 5}, {'feature': 'opened_hour_utc', 'operator': '==', 'value': '13', 'evidence': 4}, {'feature': 'opened_hour_utc', 'operator': '==', 'value': '12', 'evidence': 4}, {'feature': 'opened_hour_utc', 'operator': '==', 'value': '11', 'evidence': 4}, {'feature': 'opened_hour_utc', 'operator': '==', 'value': '10', 'evidence': 3}, {'feature': 'market_regime', 'operator': '==', 'value': 'TRENDING', 'evidence': 16}, {'feature': 'market_regime', 'operator': '==', 'value': 'HIGH_VOLATILITY', 'evidence': 13}, {'feature': 'location', 'operator': '==', 'value': 'near_support', 'evidence': 18}, {'feature': 'location', 'operator': '==', 'value': 'mid_range', 'evidence': 11}, {'feature': 'location', 'operator': '==', 'value': 'discount_zone', 'evidence': 7}, {'feature': 'location', 'operator': '==', 'value': 'premium_zone', 'evidence': 7}, {'feature': 'location', 'operator': '==', 'value': 'near_resistance', 'evidence': 6}, {'feature': 'trade_location', 'operator': '==', 'value': 'near_support', 'evidence': 18}, {'feature': 'trade_location', 'operator': '==', 'value': 'mid_range', 'evidence': 11}, {'feature': 'trade_location', 'operator': '==', 'value': 'discount_zone', 'evidence': 7}, {'feature': 'trade_location', 'operator': '==', 'value': 'premium_zone', 'evidence': 7}, {'feature': 'trade_location', 'operator': '==', 'value': 'near_resistance', 'evidence': 6}, {'feature': 'entry_zone', 'operator': '==', 'value': 'PULLBACK', 'evidence': 9}, {'feature': 'entry_zone', 'operator': '==', 'value': 'CHOPPY_RANGE', 'evidence': 8}, {'feature': 'entry_zone', 'operator': '==', 'value': 'EXHAUSTION', 'evidence': 3}, {'feature': 'entry_context', 'operator': '==', 'value': 'PULLBACK', 'evidence': 9}, {'feature': 'entry_context', 'operator': '==', 'value': 'CHOPPY_RANGE', 'evidence': 8}, {'feature': 'entry_context', 'operator': '==', 'value': 'EXHAUSTION', 'evidence': 3}, {'feature': 'score_bucket', 'operator': '==', 'value': '60-69', 'evidence': 13}, {'feature': 'score_bucket', 'operator': '==', 'value': '50-59', 'evidence': 13}, {'feature': 'score_bucket', 'operator': '==', 'value': '90-100', 'evidence': 7}, {'feature': 'score_bucket', 'operator': '==', 'value': '80-89', 'evidence': 7}, {'feature': 'score_bucket', 'operator': '==', 'value': '0-49', 'evidence': 5}, {'feature': 'score_bucket', 'operator': '==', 'value': '70-79', 'evidence': 4}, {'feature': 'rr_bucket', 'operator': '==', 'value': '2-2.99', 'evidence': 14}, {'feature': 'rr_bucket', 'operator': '==', 'value': '3+', 'evidence': 9}, {'feature': 'volume_ratio_bucket', 'operator': '==', 'value': 'high', 'evidence': 13}, {'feature': 'volume_ratio_bucket', 'operator': '==', 'value': 'normal', 'evidence': 11}, {'feature': 'volume_ratio_bucket', 'operator': '==', 'value': 'low', 'evidence': 5}, {'feature': 'rsi_bucket', 'operator': '==', 'value': 'strong', 'evidence': 14}, {'feature': 'rsi_bucket', 'operator': '==', 'value': 'weak', 'evidence': 13}, {'feature': 'rsi_bucket', 'operator': '==', 'value': 'neutral', 'evidence': 11}, {'feature': 'rsi_bucket', 'operator': '==', 'value': 'oversold', 'evidence': 9}, {'feature': 'rsi_bucket', 'operator': '==', 'value': 'overbought', 'evidence': 2}, {'feature': 'bos', 'operator': '==', 'value': 'none', 'evidence': 16}, {'feature': 'bos', 'operator': '==', 'value': 'bullish_bos', 'evidence': 10}, {'feature': 'break_of_structure', 'operator': '==', 'value': 'none', 'evidence': 16}, {'feature': 'break_of_structure', 'operator': '==', 'value': 'bullish_bos', 'evidence': 10}, {'feature': 'liquidity_sweep', 'operator': '==', 'value': 'bullish_sweep', 'evidence': 15}, {'feature': 'liquidity_sweep', 'operator': '==', 'value': 'bearish_sweep', 'evidence': 9}, {'feature': 'liquidity_distance_bucket', 'operator': '==', 'value': '1-2atr', 'evidence': 12}, {'feature': 'liquidity_distance_bucket', 'operator': '==', 'value': '4atr+', 'evidence': 5}, {'feature': 'liquidity_distance_bucket', 'operator': '==', 'value': '<1atr', 'evidence': 3}, {'feature': 'trend_4h', 'operator': '==', 'value': 'bullish', 'evidence': 18}, {'feature': 'score', 'operator': '<', 'value': 60, 'evidence': 18}, {'feature': 'score', 'operator': '>=', 'value': 70, 'evidence': 18}, {'feature': 'score', 'operator': '>=', 'value': 80, 'evidence': 14}, {'feature': 'score', 'operator': '>=', 'value': 90, 'evidence': 7}, {'feature': 'rr', 'operator': '<', 'value': 1.5, 'evidence': 0}, {'feature': 'rr', 'operator': '>=', 'value': 3, 'evidence': 9}, {'feature': 'volume_ratio', 'operator': '<', 'value': 0.8, 'evidence': 5}, {'feature': 'volume_ratio', 'operator': '<', 'value': 1.0, 'evidence': 8}, {'feature': 'rsi', 'operator': '<', 'value': 35, 'evidence': 14}, {'feature': 'rsi', 'operator': '>=', 'value': 55, 'evidence': 16}, {'feature': 'rsi', 'operator': '>=', 'value': 65, 'evidence': 4}, {'feature': 'liquidity_distance', 'operator': '<', 'value': 1, 'evidence': 3}, {'feature': 'liquidity_distance', 'operator': '>=', 'value': 4, 'evidence': 5}]
- min_evidence: 20
- near_constant_ratio: 0.98

## Eligible Conditions
| evidence | label | feature | operator | value |
| --- | --- | --- | --- | --- |
| 35 | exclude score<80 | score | < | 80 |
| 34 | exclude liquidity_distance>=2 | liquidity_distance | >= | 2 |
| 33 | exclude volume_ratio>=1.2 | volume_ratio | >= | 1.2 |
| 31 | exclude trend_4h=bearish | trend_4h | == | bearish |
| 31 | exclude score<70 | score | < | 70 |
| 29 | exclude entry_zone=BREAKOUT | entry_zone | == | BREAKOUT |
| 29 | exclude entry_context=BREAKOUT | entry_context | == | BREAKOUT |
| 29 | exclude liquidity_distance_bucket=2-4atr | liquidity_distance_bucket | == | 2-4atr |
| 28 | exclude ltf_alignment=against | ltf_alignment | == | against |
| 26 | exclude rr_bucket=1.5-1.99 | rr_bucket | == | 1.5-1.99 |
| 26 | exclude rr<2 | rr | < | 2 |
| 25 | exclude direction=long | direction | == | long |
| 25 | exclude setup=SECONDARY_SIGNAL | setup | == | SECONDARY_SIGNAL |
| 25 | exclude setup_type=SECONDARY_SIGNAL | setup_type | == | SECONDARY_SIGNAL |
| 25 | exclude liquidity_sweep=none | liquidity_sweep | == | none |
| 25 | exclude htf_alignment=against | htf_alignment | == | against |
| 25 | exclude trend_1h=bullish | trend_1h | == | bullish |
| 24 | exclude direction=short | direction | == | short |
| 24 | exclude setup=MAIN_SIGNAL | setup | == | MAIN_SIGNAL |
| 24 | exclude setup_type=MAIN_SIGNAL | setup_type | == | MAIN_SIGNAL |
| 24 | exclude htf_alignment=aligned | htf_alignment | == | aligned |
| 24 | exclude trend_1h=bearish | trend_1h | == | bearish |
| 23 | exclude bos=bearish_bos | bos | == | bearish_bos |
| 23 | exclude break_of_structure=bearish_bos | break_of_structure | == | bearish_bos |
| 23 | exclude rr>=2 | rr | >= | 2 |
| 22 | exclude rsi<45 | rsi | < | 45 |
| 21 | exclude ltf_alignment=aligned | ltf_alignment | == | aligned |
| 20 | exclude market_regime=RANGING | market_regime | == | RANGING |
| 20 | exclude volume_ratio_bucket=very_high | volume_ratio_bucket | == | very_high |
| 20 | exclude volume_ratio>=1.8 | volume_ratio | >= | 1.8 |
