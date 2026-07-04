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

## Eligible Conditions
| evidence | label | feature | operator | value |
| --- | --- | --- | --- | --- |
| 49 | exclude strategy=liquidity_sweep_mtf_v1 | strategy | == | liquidity_sweep_mtf_v1 |
| 49 | exclude paper_level=HIGH | paper_level | == | HIGH |
| 49 | exclude rr_valid=True | rr_valid | == | True |
| 49 | exclude late_entry_from_bos=False | late_entry_from_bos | == | False |
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
