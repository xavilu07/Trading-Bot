# SHADOW_SEND_CURRENT_REJECT Deep Dive

- Generated at: 2026-05-29T15:30:44+00:00
- Dataset: `data/paper_trading/trades.csv`
- Records analyzed: 40
- Shadow SEND / Current REJECT trades: 14
- Total R: 7.3887
- Winrate: 57.14%
- Profit Factor: 2.6548

## Trades

| Symbol | Session | Direction | Setup | Score | Rejection reasons | Status | R |
|---|---|---|---|---:|---|---|---:|
| BTCUSDT | OVERLAP | LONG | MAIN_SIGNAL | 65.0 | breakout_bad_location | sl_hit | -1.0 |
| BTCUSDT | OVERLAP | LONG | MAIN_SIGNAL | 65.0 | breakout_bad_location | tp2_hit | 4.2552 |
| BNBUSDT | OVERLAP | LONG | MAIN_SIGNAL | 55.0 | market_regime_ranging/against_htf/edge_activation_requires_trending | sl_hit | -1.0 |
| AVAXUSDT | OVERLAP | LONG | MAIN_SIGNAL | 55.0 | market_regime_ranging/against_htf/edge_activation_requires_trending | tp2_hit | 1.5068 |
| XRPUSDT | OVERLAP | LONG | MAIN_SIGNAL | 45.0 | market_regime_ranging/breakout_bad_location/against_htf/edge_activation_requires_trending | sl_hit | -1.0 |
| DOGEUSDT | LONDON | LONG | MAIN_SIGNAL | 55.0 | market_regime_ranging/entry_context_choppy_range/low_volume/dirty_sideways_market/edge_activation_requires_trending/edge_activation_requires_overlap_session/edge_activation_choppy_range | expired | 1.0 |
| DOGEUSDT | OVERLAP | LONG | SECONDARY_SIGNAL | 90.0 | setup_type_secondary_signal/edge_activation_secondary_signal | expired | -0.2855 |
| ETHUSDT | NEW_YORK | LONG | SECONDARY_SIGNAL | 60.0 | market_regime_ranging/breakout_bad_location/setup_type_secondary_signal/edge_activation_requires_trending/edge_activation_requires_overlap_session/edge_activation_secondary_signal | expired | 0.6813 |
| AVAXUSDT | NEW_YORK | LONG | SECONDARY_SIGNAL | 80.0 | market_regime_ranging/entry_context_choppy_range/trade_location_premium_zone/setup_type_secondary_signal/against_htf/low_volume/dirty_sideways_market/edge_activation_requires_trending/edge_activation_requires_overlap_session/edge_activation_choppy_range/edge_activation_premium_zone/edge_activation_secondary_signal | expired | 0.4104 |
| DOTUSDT | NEW_YORK | LONG | SECONDARY_SIGNAL | 55.0 | setup_type_secondary_signal/against_htf/edge_activation_requires_overlap_session/edge_activation_secondary_signal | tp2_hit | 1.5 |
| BTCUSDT | LONDON | LONG | MAIN_SIGNAL | 70.0 | market_regime_ranging/edge_activation_requires_trending/edge_activation_requires_overlap_session | expired | 1.0 |
| ETHUSDT | LONDON | SHORT | SECONDARY_SIGNAL | 80.0 | market_regime_not_trending/setup_type_secondary_signal/short_shadow_mode/short_without_high_historical_edge/against_htf/edge_activation_requires_trending/edge_activation_requires_overlap_session/edge_activation_requires_long/edge_activation_secondary_signal | expired | -0.1795 |
| BNBUSDT | LONDON | SHORT | MAIN_SIGNAL | 50.0 | short_shadow_mode/short_without_high_historical_edge/edge_activation_requires_overlap_session/edge_activation_requires_long | sl_hit | -1.0 |
| BNBUSDT | LONDON | LONG | MAIN_SIGNAL | 50.0 | breakout_bad_location/against_htf/edge_activation_requires_overlap_session | tp2_hit | 1.5 |

## Rejection Reasons Destroying Edge

| Reason | Classification | n | Total R | WR | AvgR | PF | Recommendation |
|---|---|---:|---:|---:|---:|---:|---|
| edge_activation_requires_overlap_session | SAFE_TO_RELAX | 8 | 4.9122 | 75.0% | 0.614 | 5.1646 | Candidate for controlled shadow/public relaxation; validate with forward sample first. |
| breakout_bad_location | SAFE_TO_RELAX | 5 | 4.4365 | 60.0% | 0.8873 | 3.2183 | Candidate for controlled shadow/public relaxation; validate with forward sample first. |
| against_htf | SAFE_TO_RELAX | 7 | 2.7377 | 57.14% | 0.3911 | 2.2561 | Candidate for controlled shadow/public relaxation; validate with forward sample first. |
| market_regime_ranging | SAFE_TO_RELAX | 7 | 2.5985 | 71.43% | 0.3712 | 2.2992 | Candidate for controlled shadow/public relaxation; validate with forward sample first. |
| edge_activation_requires_trending | SAFE_TO_RELAX | 8 | 2.419 | 62.5% | 0.3024 | 2.1099 | Candidate for controlled shadow/public relaxation; validate with forward sample first. |
| setup_type_secondary_signal | SAFE_TO_RELAX | 5 | 2.1267 | 60.0% | 0.4253 | 5.5735 | Candidate for controlled shadow/public relaxation; validate with forward sample first. |
| edge_activation_secondary_signal | SAFE_TO_RELAX | 5 | 2.1267 | 60.0% | 0.4253 | 5.5735 | Candidate for controlled shadow/public relaxation; validate with forward sample first. |
| entry_context_choppy_range | NEED_MORE_DATA | 2 | 1.4104 | 100.0% | 0.7052 | 1.4104 | Keep in shadow; sample is not strong enough for production relaxation. |
| low_volume | NEED_MORE_DATA | 2 | 1.4104 | 100.0% | 0.7052 | 1.4104 | Keep in shadow; sample is not strong enough for production relaxation. |
| dirty_sideways_market | NEED_MORE_DATA | 2 | 1.4104 | 100.0% | 0.7052 | 1.4104 | Keep in shadow; sample is not strong enough for production relaxation. |
| edge_activation_choppy_range | NEED_MORE_DATA | 2 | 1.4104 | 100.0% | 0.7052 | 1.4104 | Keep in shadow; sample is not strong enough for production relaxation. |
| trade_location_premium_zone | NEED_MORE_DATA | 1 | 0.4104 | 100.0% | 0.4104 | 0.4104 | Keep in shadow; sample is not strong enough for production relaxation. |
| edge_activation_premium_zone | NEED_MORE_DATA | 1 | 0.4104 | 100.0% | 0.4104 | 0.4104 | Keep in shadow; sample is not strong enough for production relaxation. |
| market_regime_not_trending | NEED_MORE_DATA | 1 | -0.1795 | 0.0% | -0.1795 | 0.0 | Keep in shadow; sample is not strong enough for production relaxation. |
| short_shadow_mode | NEED_MORE_DATA | 2 | -1.1795 | 0.0% | -0.5897 | 0.0 | Keep in shadow; sample is not strong enough for production relaxation. |
| short_without_high_historical_edge | NEED_MORE_DATA | 2 | -1.1795 | 0.0% | -0.5897 | 0.0 | Keep in shadow; sample is not strong enough for production relaxation. |
| edge_activation_requires_long | NEED_MORE_DATA | 2 | -1.1795 | 0.0% | -0.5897 | 0.0 | Keep in shadow; sample is not strong enough for production relaxation. |
