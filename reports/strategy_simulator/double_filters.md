# Double Filters

| conditions | trades_remaining | trades_eliminated | remaining_closed | removed_closed | winrate | profit_factor | total_r | expectancy | drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ["exclude setup=SECONDARY_SIGNAL", "exclude setup_type=SECONDARY_SIGNAL"] | 24 | 25 | 24 | 25 | 37.5 | 1.1336 | 1.8698 | 0.0779 | -6.0 |
| ["exclude setup=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | 24 | 25 | 24 | 25 | 37.5 | 1.1336 | 1.8698 | 0.0779 | -6.0 |
| ["exclude setup_type=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | 24 | 25 | 24 | 25 | 37.5 | 1.1336 | 1.8698 | 0.0779 | -6.0 |
| ["exclude bos=bearish_bos", "exclude break_of_structure=bearish_bos"] | 26 | 23 | 26 | 23 | 38.4615 | 1.0429 | 0.5203 | 0.02 | -4.3472 |
| ["exclude volume_ratio_bucket=very_high", "exclude volume_ratio>=1.8"] | 29 | 20 | 29 | 20 | 41.3793 | 0.8711 | -1.6663 | -0.0575 | -5.2499 |
| ["exclude trend_1h=bearish", "exclude rsi<45"] | 22 | 27 | 22 | 27 | 31.8182 | 0.7919 | -2.5312 | -0.1151 | -6.5927 |
| ["exclude htf_alignment=aligned", "exclude ltf_alignment=aligned"] | 21 | 28 | 21 | 28 | 28.5714 | 0.7352 | -2.6559 | -0.1265 | -6.3209 |
| ["exclude entry_zone=BREAKOUT", "exclude entry_context=BREAKOUT"] | 20 | 29 | 20 | 29 | 30.0 | 0.7104 | -3.475 | -0.1738 | -6.0828 |
| ["exclude rr_bucket=1.5-1.99", "exclude rr<2"] | 23 | 26 | 23 | 26 | 26.087 | 0.6601 | -4.8408 | -0.2105 | -5.7918 |
| ["exclude setup=MAIN_SIGNAL", "exclude setup_type=MAIN_SIGNAL"] | 25 | 24 | 25 | 24 | 36.0 | 0.5951 | -3.9481 | -0.1579 | -4.686 |
