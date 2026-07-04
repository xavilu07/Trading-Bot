# Worst Configs

| conditions | trades_remaining | trades_eliminated | remaining_closed | removed_closed | winrate | profit_factor | total_r | expectancy | drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ["exclude direction=long"] | 24 | 25 | 24 | 25 | 25.0 | 0.391 | -8.9028 | -0.3709 | -10.4643 |
| ["exclude rr_bucket=1.5-1.99"] | 23 | 26 | 23 | 26 | 26.087 | 0.6601 | -4.8408 | -0.2105 | -5.7918 |
| ["exclude rr<2"] | 23 | 26 | 23 | 26 | 26.087 | 0.6601 | -4.8408 | -0.2105 | -5.7918 |
| ["exclude rr_bucket=1.5-1.99", "exclude rr<2"] | 23 | 26 | 23 | 26 | 26.087 | 0.6601 | -4.8408 | -0.2105 | -5.7918 |
| ["exclude htf_alignment=against"] | 24 | 25 | 24 | 25 | 33.3333 | 0.6777 | -4.4224 | -0.1843 | -8.3528 |
| ["exclude ltf_alignment=aligned"] | 28 | 21 | 28 | 21 | 25.0 | 0.7255 | -4.4007 | -0.1572 | -8.8277 |
| ["exclude setup=MAIN_SIGNAL"] | 25 | 24 | 25 | 24 | 36.0 | 0.5951 | -3.9481 | -0.1579 | -4.686 |
| ["exclude setup_type=MAIN_SIGNAL"] | 25 | 24 | 25 | 24 | 36.0 | 0.5951 | -3.9481 | -0.1579 | -4.686 |
| ["exclude setup=MAIN_SIGNAL", "exclude setup_type=MAIN_SIGNAL"] | 25 | 24 | 25 | 24 | 36.0 | 0.5951 | -3.9481 | -0.1579 | -4.686 |
| ["exclude entry_zone=BREAKOUT"] | 20 | 29 | 20 | 29 | 30.0 | 0.7104 | -3.475 | -0.1738 | -6.0828 |
| ["exclude entry_context=BREAKOUT"] | 20 | 29 | 20 | 29 | 30.0 | 0.7104 | -3.475 | -0.1738 | -6.0828 |
| ["exclude entry_zone=BREAKOUT", "exclude entry_context=BREAKOUT"] | 20 | 29 | 20 | 29 | 30.0 | 0.7104 | -3.475 | -0.1738 | -6.0828 |
| ["exclude rsi<45"] | 27 | 22 | 27 | 22 | 33.3333 | 0.7884 | -3.0983 | -0.1148 | -8.1823 |
| ["exclude htf_alignment=aligned", "exclude ltf_alignment=aligned"] | 21 | 28 | 21 | 28 | 28.5714 | 0.7352 | -2.6559 | -0.1265 | -6.3209 |
| ["exclude trend_1h=bearish", "exclude rsi<45"] | 22 | 27 | 22 | 27 | 31.8182 | 0.7919 | -2.5312 | -0.1151 | -6.5927 |
| ["exclude trend_1h=bearish"] | 25 | 24 | 25 | 24 | 36.0 | 0.8383 | -2.128 | -0.0851 | -6.1895 |
| ["exclude volume_ratio_bucket=very_high"] | 29 | 20 | 29 | 20 | 41.3793 | 0.8711 | -1.6663 | -0.0575 | -5.2499 |
| ["exclude volume_ratio>=1.8"] | 29 | 20 | 29 | 20 | 41.3793 | 0.8711 | -1.6663 | -0.0575 | -5.2499 |
| ["exclude volume_ratio_bucket=very_high", "exclude volume_ratio>=1.8"] | 29 | 20 | 29 | 20 | 41.3793 | 0.8711 | -1.6663 | -0.0575 | -5.2499 |
| ["exclude trend_1h=bullish"] | 24 | 25 | 24 | 25 | 37.5 | 1.0047 | 0.0497 | 0.0021 | -3.7252 |
| ["exclude bos=bearish_bos"] | 26 | 23 | 26 | 23 | 38.4615 | 1.0429 | 0.5203 | 0.02 | -4.3472 |
| ["exclude break_of_structure=bearish_bos"] | 26 | 23 | 26 | 23 | 38.4615 | 1.0429 | 0.5203 | 0.02 | -4.3472 |
| ["exclude bos=bearish_bos", "exclude break_of_structure=bearish_bos"] | 26 | 23 | 26 | 23 | 38.4615 | 1.0429 | 0.5203 | 0.02 | -4.3472 |
| ["exclude market_regime=RANGING"] | 29 | 20 | 29 | 20 | 34.4828 | 1.1121 | 1.4873 | 0.0513 | -4.2517 |
| ["exclude setup=SECONDARY_SIGNAL"] | 24 | 25 | 24 | 25 | 37.5 | 1.1336 | 1.8698 | 0.0779 | -6.0 |
| ["exclude setup_type=SECONDARY_SIGNAL"] | 24 | 25 | 24 | 25 | 37.5 | 1.1336 | 1.8698 | 0.0779 | -6.0 |
| ["exclude liquidity_sweep=none"] | 24 | 25 | 24 | 25 | 37.5 | 1.1336 | 1.8698 | 0.0779 | -6.0 |
| ["exclude setup=SECONDARY_SIGNAL", "exclude setup_type=SECONDARY_SIGNAL"] | 24 | 25 | 24 | 25 | 37.5 | 1.1336 | 1.8698 | 0.0779 | -6.0 |
| ["exclude setup=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | 24 | 25 | 24 | 25 | 37.5 | 1.1336 | 1.8698 | 0.0779 | -6.0 |
| ["exclude setup_type=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | 24 | 25 | 24 | 25 | 37.5 | 1.1336 | 1.8698 | 0.0779 | -6.0 |
| ["exclude setup=SECONDARY_SIGNAL", "exclude setup_type=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | 24 | 25 | 24 | 25 | 37.5 | 1.1336 | 1.8698 | 0.0779 | -6.0 |
| ["exclude ltf_alignment=against"] | 21 | 28 | 21 | 28 | 52.381 | 1.3008 | 2.3224 | 0.1106 | -3.8472 |
| ["exclude htf_alignment=aligned"] | 25 | 24 | 25 | 24 | 40.0 | 1.2337 | 2.3441 | 0.0938 | -4.7241 |
| ["exclude rr>=2"] | 26 | 23 | 26 | 23 | 46.1538 | 1.2905 | 2.7625 | 0.1063 | -3.9808 |
| ["exclude direction=short"] | 25 | 24 | 25 | 24 | 48.0 | 1.7473 | 6.8245 | 0.273 | -2.3432 |
| ["exclude liquidity_distance_bucket=2-4atr"] | 20 | 29 | 20 | 29 | 55.0 | 2.6415 | 7.8114 | 0.3906 | -2.0 |
