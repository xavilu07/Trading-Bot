# Best Configs

| conditions | trades_remaining | trades_eliminated | remaining_closed | removed_closed | winrate | profit_factor | total_r | expectancy | drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ["exclude volume_ratio>=1.2", "exclude entry_zone=BREAKOUT"] | 23 | 26 | 23 | 26 | 43.4783 | 1.5234 | 4.2444 | 0.1845 | -2.382 |
| ["exclude volume_ratio>=1.2", "exclude entry_context=BREAKOUT"] | 23 | 26 | 23 | 26 | 43.4783 | 1.5234 | 4.2444 | 0.1845 | -2.382 |
| ["exclude volume_ratio>=1.2", "exclude entry_zone=BREAKOUT", "exclude entry_context=BREAKOUT"] | 23 | 26 | 23 | 26 | 43.4783 | 1.5234 | 4.2444 | 0.1845 | -2.382 |
| ["exclude setup=MAIN_SIGNAL", "exclude setup_type=MAIN_SIGNAL"] | 24 | 25 | 24 | 25 | 37.5 | 1.1336 | 1.8698 | 0.0779 | -6.0 |
| ["exclude entry_zone=BREAKOUT", "exclude entry_context=BREAKOUT"] | 29 | 20 | 29 | 20 | 41.3793 | 1.1189 | 1.3967 | 0.0482 | -3.4759 |
| ["exclude volume_ratio>=1.2", "exclude volume_ratio_bucket=very_high"] | 20 | 29 | 20 | 29 | 30.0 | 0.9619 | -0.412 | -0.0206 | -6.0525 |
| ["exclude volume_ratio>=1.2", "exclude volume_ratio>=1.8"] | 20 | 29 | 20 | 29 | 30.0 | 0.9619 | -0.412 | -0.0206 | -6.0525 |
| ["exclude volume_ratio_bucket=very_high", "exclude volume_ratio>=1.8"] | 20 | 29 | 20 | 29 | 30.0 | 0.9619 | -0.412 | -0.0206 | -6.0525 |
| ["exclude volume_ratio>=1.2", "exclude volume_ratio_bucket=very_high", "exclude volume_ratio>=1.8"] | 20 | 29 | 20 | 29 | 30.0 | 0.9619 | -0.412 | -0.0206 | -6.0525 |
| ["exclude liquidity_distance>=2", "exclude entry_zone=BREAKOUT"] | 20 | 29 | 20 | 29 | 40.0 | 0.9511 | -0.4757 | -0.0238 | -4.5903 |
| ["exclude liquidity_distance>=2", "exclude entry_context=BREAKOUT"] | 20 | 29 | 20 | 29 | 40.0 | 0.9511 | -0.4757 | -0.0238 | -4.5903 |
| ["exclude liquidity_distance>=2", "exclude entry_zone=BREAKOUT", "exclude entry_context=BREAKOUT"] | 20 | 29 | 20 | 29 | 40.0 | 0.9511 | -0.4757 | -0.0238 | -4.5903 |
| ["exclude entry_zone=BREAKOUT", "exclude bos=bearish_bos"] | 21 | 28 | 21 | 28 | 38.0952 | 0.9378 | -0.5986 | -0.0285 | -4.5245 |
| ["exclude entry_zone=BREAKOUT", "exclude break_of_structure=bearish_bos"] | 21 | 28 | 21 | 28 | 38.0952 | 0.9378 | -0.5986 | -0.0285 | -4.5245 |
| ["exclude entry_context=BREAKOUT", "exclude bos=bearish_bos"] | 21 | 28 | 21 | 28 | 38.0952 | 0.9378 | -0.5986 | -0.0285 | -4.5245 |
| ["exclude entry_context=BREAKOUT", "exclude break_of_structure=bearish_bos"] | 21 | 28 | 21 | 28 | 38.0952 | 0.9378 | -0.5986 | -0.0285 | -4.5245 |
| ["exclude entry_zone=BREAKOUT", "exclude entry_context=BREAKOUT", "exclude bos=bearish_bos"] | 21 | 28 | 21 | 28 | 38.0952 | 0.9378 | -0.5986 | -0.0285 | -4.5245 |
| ["exclude entry_zone=BREAKOUT", "exclude entry_context=BREAKOUT", "exclude break_of_structure=bearish_bos"] | 21 | 28 | 21 | 28 | 38.0952 | 0.9378 | -0.5986 | -0.0285 | -4.5245 |
| ["exclude entry_zone=BREAKOUT", "exclude bos=bearish_bos", "exclude break_of_structure=bearish_bos"] | 21 | 28 | 21 | 28 | 38.0952 | 0.9378 | -0.5986 | -0.0285 | -4.5245 |
| ["exclude entry_context=BREAKOUT", "exclude bos=bearish_bos", "exclude break_of_structure=bearish_bos"] | 21 | 28 | 21 | 28 | 38.0952 | 0.9378 | -0.5986 | -0.0285 | -4.5245 |
| ["exclude volume_ratio>=1.2", "exclude trend_4h=bearish"] | 21 | 28 | 21 | 28 | 38.0952 | 0.9044 | -0.9163 | -0.0436 | -4.7206 |
| ["exclude bos=bearish_bos", "exclude break_of_structure=bearish_bos"] | 23 | 26 | 23 | 26 | 34.7826 | 0.7763 | -2.5986 | -0.113 | -5.5245 |
| ["exclude ltf_alignment=against", "exclude htf_alignment=against"] | 21 | 28 | 21 | 28 | 28.5714 | 0.7352 | -2.6559 | -0.1265 | -6.3209 |
| ["exclude liquidity_distance>=2", "exclude volume_ratio>=1.2"] | 25 | 24 | 25 | 24 | 28.0 | 0.6867 | -4.6125 | -0.1845 | -7.6425 |
| ["exclude trend_4h=bearish", "exclude trend_1h=bearish"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6657 | -3.2055 | -0.1457 | -4.453 |
| ["exclude liquidity_distance>=2", "exclude rr>=2"] | 21 | 28 | 21 | 28 | 23.8095 | 0.6344 | -4.8408 | -0.2305 | -5.7918 |
| ["exclude liquidity_distance>=2", "exclude htf_alignment=aligned"] | 20 | 29 | 20 | 29 | 30.0 | 0.6227 | -4.4224 | -0.2211 | -7.3528 |
| ["exclude liquidity_distance>=2", "exclude ltf_alignment=against"] | 20 | 29 | 20 | 29 | 20.0 | 0.6206 | -5.6903 | -0.2845 | -10.0 |
| ["exclude entry_zone=BREAKOUT", "exclude setup=SECONDARY_SIGNAL"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_zone=BREAKOUT", "exclude setup_type=SECONDARY_SIGNAL"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_zone=BREAKOUT", "exclude liquidity_sweep=none"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_context=BREAKOUT", "exclude setup=SECONDARY_SIGNAL"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_context=BREAKOUT", "exclude setup_type=SECONDARY_SIGNAL"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_context=BREAKOUT", "exclude liquidity_sweep=none"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_zone=BREAKOUT", "exclude entry_context=BREAKOUT", "exclude setup=SECONDARY_SIGNAL"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_zone=BREAKOUT", "exclude entry_context=BREAKOUT", "exclude setup_type=SECONDARY_SIGNAL"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_zone=BREAKOUT", "exclude entry_context=BREAKOUT", "exclude liquidity_sweep=none"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_zone=BREAKOUT", "exclude setup=SECONDARY_SIGNAL", "exclude setup_type=SECONDARY_SIGNAL"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_zone=BREAKOUT", "exclude setup=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_zone=BREAKOUT", "exclude setup_type=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_context=BREAKOUT", "exclude setup=SECONDARY_SIGNAL", "exclude setup_type=SECONDARY_SIGNAL"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_context=BREAKOUT", "exclude setup=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude entry_context=BREAKOUT", "exclude setup_type=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | 22 | 27 | 22 | 27 | 36.3636 | 0.6162 | -3.3585 | -0.1527 | -3.8052 |
| ["exclude setup=SECONDARY_SIGNAL", "exclude setup_type=SECONDARY_SIGNAL"] | 25 | 24 | 25 | 24 | 36.0 | 0.5951 | -3.9481 | -0.1579 | -4.686 |
| ["exclude setup=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | 25 | 24 | 25 | 24 | 36.0 | 0.5951 | -3.9481 | -0.1579 | -4.686 |
| ["exclude setup_type=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | 25 | 24 | 25 | 24 | 36.0 | 0.5951 | -3.9481 | -0.1579 | -4.686 |
| ["exclude setup=SECONDARY_SIGNAL", "exclude setup_type=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | 25 | 24 | 25 | 24 | 36.0 | 0.5951 | -3.9481 | -0.1579 | -4.686 |
| ["exclude liquidity_distance>=2", "exclude liquidity_distance_bucket=2-4atr"] | 29 | 20 | 29 | 20 | 24.1379 | 0.4793 | -9.8897 | -0.341 | -12.7874 |
| ["exclude liquidity_distance>=2", "exclude trend_4h=bearish"] | 23 | 26 | 23 | 26 | 30.4348 | 0.439 | -7.6227 | -0.3314 | -9.5694 |
| ["exclude volume_ratio>=1.2", "exclude liquidity_distance_bucket=2-4atr"] | 22 | 27 | 22 | 27 | 22.7273 | 0.4077 | -8.2874 | -0.3767 | -9.7874 |
| ["exclude liquidity_distance>=2", "exclude volume_ratio>=1.2", "exclude liquidity_distance_bucket=2-4atr"] | 22 | 27 | 22 | 27 | 22.7273 | 0.4077 | -8.2874 | -0.3767 | -9.7874 |
