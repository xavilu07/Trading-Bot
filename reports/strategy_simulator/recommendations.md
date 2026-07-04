# Recommendations

| conditions | action | expected_pf | expected_total_r | trades_lost | confidence | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| ["exclude liquidity_distance_bucket=2-4atr"] | Simulate filter before production | 2.6415 | 7.8114 | 29 | LOW | 20 |
| ["exclude direction=short"] | Simulate filter before production | 1.7473 | 6.8245 | 24 | LOW | 25 |
| ["exclude ltf_alignment=against"] | Simulate filter before production | 1.3008 | 2.3224 | 28 | LOW | 21 |
| ["exclude rr>=2"] | Simulate filter before production | 1.2905 | 2.7625 | 23 | LOW | 26 |
| ["exclude htf_alignment=aligned"] | Simulate filter before production | 1.2337 | 2.3441 | 24 | LOW | 25 |
| ["exclude setup=SECONDARY_SIGNAL"] | Simulate filter before production | 1.1336 | 1.8698 | 25 | LOW | 24 |
| ["exclude setup_type=SECONDARY_SIGNAL"] | Simulate filter before production | 1.1336 | 1.8698 | 25 | LOW | 24 |
| ["exclude liquidity_sweep=none"] | Simulate filter before production | 1.1336 | 1.8698 | 25 | LOW | 24 |
| ["exclude setup=SECONDARY_SIGNAL", "exclude setup_type=SECONDARY_SIGNAL"] | Simulate filter before production | 1.1336 | 1.8698 | 25 | LOW | 24 |
| ["exclude setup=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | Simulate filter before production | 1.1336 | 1.8698 | 25 | LOW | 24 |
| ["exclude setup_type=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | Simulate filter before production | 1.1336 | 1.8698 | 25 | LOW | 24 |
| ["exclude setup=SECONDARY_SIGNAL", "exclude setup_type=SECONDARY_SIGNAL", "exclude liquidity_sweep=none"] | Simulate filter before production | 1.1336 | 1.8698 | 25 | LOW | 24 |
| ["exclude market_regime=RANGING"] | Simulate filter before production | 1.1121 | 1.4873 | 20 | LOW | 29 |
| ["exclude bos=bearish_bos"] | Simulate filter before production | 1.0429 | 0.5203 | 23 | LOW | 26 |
| ["exclude break_of_structure=bearish_bos"] | Simulate filter before production | 1.0429 | 0.5203 | 23 | LOW | 26 |
| ["exclude bos=bearish_bos", "exclude break_of_structure=bearish_bos"] | Simulate filter before production | 1.0429 | 0.5203 | 23 | LOW | 26 |
| ["exclude trend_1h=bullish"] | Simulate filter before production | 1.0047 | 0.0497 | 25 | LOW | 24 |
| ["exclude volume_ratio_bucket=very_high"] | Simulate filter before production | 0.8711 | -1.6663 | 20 | LOW | 29 |
| ["exclude volume_ratio>=1.8"] | Simulate filter before production | 0.8711 | -1.6663 | 20 | LOW | 29 |
| ["exclude volume_ratio_bucket=very_high", "exclude volume_ratio>=1.8"] | Simulate filter before production | 0.8711 | -1.6663 | 20 | LOW | 29 |
| ["exclude volume_ratio>=1.2", "exclude entry_zone=BREAKOUT"] | Prioritize configuration in shadow | 1.5234 | 4.2444 | 26 | LOW | 23 |
| ["exclude volume_ratio>=1.2", "exclude entry_context=BREAKOUT"] | Prioritize configuration in shadow | 1.5234 | 4.2444 | 26 | LOW | 23 |
| ["exclude volume_ratio>=1.2", "exclude entry_zone=BREAKOUT", "exclude entry_context=BREAKOUT"] | Prioritize configuration in shadow | 1.5234 | 4.2444 | 26 | LOW | 23 |
| ["exclude setup=MAIN_SIGNAL", "exclude setup_type=MAIN_SIGNAL"] | Prioritize configuration in shadow | 1.1336 | 1.8698 | 25 | LOW | 24 |
| ["exclude entry_zone=BREAKOUT", "exclude entry_context=BREAKOUT"] | Prioritize configuration in shadow | 1.1189 | 1.3967 | 20 | LOW | 29 |
| ["exclude volume_ratio>=1.2", "exclude volume_ratio_bucket=very_high"] | Prioritize configuration in shadow | 0.9619 | -0.412 | 29 | LOW | 20 |
| ["exclude volume_ratio>=1.2", "exclude volume_ratio>=1.8"] | Prioritize configuration in shadow | 0.9619 | -0.412 | 29 | LOW | 20 |
| ["exclude volume_ratio_bucket=very_high", "exclude volume_ratio>=1.8"] | Prioritize configuration in shadow | 0.9619 | -0.412 | 29 | LOW | 20 |
| ["exclude volume_ratio>=1.2", "exclude volume_ratio_bucket=very_high", "exclude volume_ratio>=1.8"] | Prioritize configuration in shadow | 0.9619 | -0.412 | 29 | LOW | 20 |
| ["exclude liquidity_distance>=2", "exclude entry_zone=BREAKOUT"] | Prioritize configuration in shadow | 0.9511 | -0.4757 | 29 | LOW | 20 |
