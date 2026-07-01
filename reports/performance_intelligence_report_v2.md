# Performance Intelligence Report V2

Generated at: 2026-07-01T14:29:20+00:00
Source: `data/paper_trading/trades.csv`

## 1. Executive Summary

- Closed/evaluable trades: 41
- Open trades kept separate: 8
- Total R: -2.5754
- Avg R: -0.0628
- Winrate: 34.1463%
- Profit factor: 0.8876
- Score effectiveness: INSUFFICIENT_DATA
- Direction behavior: LONG_OUTPERFORMS_SHORT
- Expired conclusion: MANY_POSITIVE_EXPIRED_CHECK_TP_CALIBRATION

## 2. Global Performance

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| GLOBAL | ALL_CLOSED | 41 | -2.5754 | -0.0628 | 34.1463% | 0.8876 | 14/27/0 | 13 | 7 | 20 | HIGH | WATCH |

### Status Distribution

| Value | Count |
|---|---:|
| sl_hit | 20 |
| expired | 13 |
| open | 8 |
| tp2_hit | 7 |
| tp1_hit | 1 |

## 3. Best Edges

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| direction | long | 20 | 7.225 | 0.3613 | 55.0% | 1.872 | 11/9/0 | 6 | 5 | 8 | MEDIUM | WATCH |
| direction + setup_type | long + MAIN_SIGNAL | 15 | 5.9188 | 0.3946 | 53.3333% | 1.8455 | 8/7/0 | 3 | 4 | 7 | MEDIUM | WATCH |
| nearest_distance_to_liquidity_atr_bucket | 0.5-1 | 15 | 5.1977 | 0.3465 | 46.6667% | 1.7041 | 7/8/0 | 3 | 4 | 7 | MEDIUM | WATCH |
| setup_type | MAIN_SIGNAL | 23 | 1.8698 | 0.0813 | 39.1304% | 1.1336 | 9/14/0 | 3 | 5 | 14 | MEDIUM | WATCH |
| trend_4h | bullish | 16 | 1.5712 | 0.0982 | 31.25% | 1.1889 | 5/11/0 | 7 | 2 | 7 | MEDIUM | WATCH |
| trade_location | near_support | 15 | 1.5189 | 0.1013 | 40.0% | 1.1873 | 6/9/0 | 4 | 3 | 7 | MEDIUM | WATCH |
| entry_context | BREAKOUT | 23 | 0.8996 | 0.0391 | 34.7826% | 1.0825 | 8/15/0 | 11 | 4 | 8 | MEDIUM | WATCH |

## 4. Worst Edges

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| direction | short | 21 | -9.8004 | -0.4667 | 14.2857% | 0.3296 | 3/18/0 | 7 | 2 | 12 | MEDIUM | WATCH |
| nearest_distance_to_liquidity_atr_bucket | 1-2 | 20 | -6.2266 | -0.3113 | 25.0% | 0.472 | 5/15/0 | 8 | 2 | 10 | MEDIUM | WATCH |
| directional_distance_to_liquidity_atr_bucket | 2-3 | 19 | -5.311 | -0.2795 | 26.3158% | 0.6002 | 5/14/0 | 2 | 4 | 13 | MEDIUM | WATCH |
| liquidity_sweep | none | 18 | -4.4452 | -0.247 | 27.7778% | 0.5007 | 5/13/0 | 10 | 2 | 6 | MEDIUM | WATCH |
| setup_type | SECONDARY_SIGNAL | 18 | -4.4452 | -0.247 | 27.7778% | 0.5007 | 5/13/0 | 10 | 2 | 6 | MEDIUM | WATCH |
| trend_4h | bearish | 25 | -4.1466 | -0.1659 | 36.0% | 0.7157 | 9/16/0 | 6 | 5 | 13 | MEDIUM | WATCH |
| market_regime | RANGING | 18 | -4.0123 | -0.2229 | 38.8889% | 0.6171 | 7/11/0 | 6 | 2 | 10 | MEDIUM | WATCH |
| break_of_structure | bearish_bos | 20 | -3.4962 | -0.1748 | 25.0% | 0.6991 | 5/15/0 | 9 | 2 | 9 | MEDIUM | WATCH |
| late_entry_from_bos | false | 41 | -2.5754 | -0.0628 | 34.1463% | 0.8876 | 14/27/0 | 13 | 7 | 20 | HIGH | WATCH |
| paper_level | HIGH | 41 | -2.5754 | -0.0628 | 34.1463% | 0.8876 | 14/27/0 | 13 | 7 | 20 | HIGH | WATCH |
| rr_valid | true | 41 | -2.5754 | -0.0628 | 34.1463% | 0.8876 | 14/27/0 | 13 | 7 | 20 | HIGH | WATCH |
| break_of_structure | none | 15 | -1.8854 | -0.1257 | 33.3333% | 0.8115 | 5/10/0 | 1 | 3 | 10 | MEDIUM | WATCH |
| trend_1h | bullish | 23 | -1.684 | -0.0732 | 34.7826% | 0.8633 | 8/15/0 | 8 | 3 | 11 | MEDIUM | WATCH |
| trend_1h | bearish | 18 | -0.8914 | -0.0495 | 33.3333% | 0.9158 | 6/12/0 | 5 | 4 | 9 | MEDIUM | WATCH |

## 5. Expired Trades Analysis

- Expired share: 31.7073%
- Positive expired count: 6
- Positive expired Total R: 4.4584

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| status | expired | 13 | 1.5548 | 0.1196 | 46.1538% | 1.5355 | 6/7/0 | 13 | 0 | 0 | LOW | INSUFFICIENT_DATA |

### Top Expired Contexts

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| late_entry_from_bos | false | 41 | -2.5754 | -0.0628 | 34.1463% | 0.8876 | 14/27/0 | 13 | 7 | 20 | HIGH | WATCH |
| paper_level | HIGH | 41 | -2.5754 | -0.0628 | 34.1463% | 0.8876 | 14/27/0 | 13 | 7 | 20 | HIGH | WATCH |
| rr_valid | true | 41 | -2.5754 | -0.0628 | 34.1463% | 0.8876 | 14/27/0 | 13 | 7 | 20 | HIGH | WATCH |
| entry_context | BREAKOUT | 23 | 0.8996 | 0.0391 | 34.7826% | 1.0825 | 8/15/0 | 11 | 4 | 8 | MEDIUM | WATCH |
| liquidity_sweep | none | 18 | -4.4452 | -0.247 | 27.7778% | 0.5007 | 5/13/0 | 10 | 2 | 6 | MEDIUM | WATCH |
| setup_type | SECONDARY_SIGNAL | 18 | -4.4452 | -0.247 | 27.7778% | 0.5007 | 5/13/0 | 10 | 2 | 6 | MEDIUM | WATCH |
| break_of_structure | bearish_bos | 20 | -3.4962 | -0.1748 | 25.0% | 0.6991 | 5/15/0 | 9 | 2 | 9 | MEDIUM | WATCH |
| trend_1h | bullish | 23 | -1.684 | -0.0732 | 34.7826% | 0.8633 | 8/15/0 | 8 | 3 | 11 | MEDIUM | WATCH |
| nearest_distance_to_liquidity_atr_bucket | 1-2 | 20 | -6.2266 | -0.3113 | 25.0% | 0.472 | 5/15/0 | 8 | 2 | 10 | MEDIUM | WATCH |
| direction | short | 21 | -9.8004 | -0.4667 | 14.2857% | 0.3296 | 3/18/0 | 7 | 2 | 12 | MEDIUM | WATCH |

## 6. Score Effectiveness

- Conclusion: INSUFFICIENT_DATA

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| score_bucket | 0-49 | 5 | -5.0 | -1.0 | 0.0% | 0.0 | 0/5/0 | 0 | 0 | 5 | LOW | INSUFFICIENT_DATA |
| score_bucket | 50-59 | 12 | 1.9803 | 0.165 | 41.6667% | 1.3057 | 5/7/0 | 2 | 4 | 6 | LOW | INSUFFICIENT_DATA |
| score_bucket | 60-69 | 11 | 1.96 | 0.1782 | 45.4545% | 1.3267 | 5/6/0 | 3 | 2 | 6 | LOW | INSUFFICIENT_DATA |
| score_bucket | 70-79 | 2 | 2.0 | 1.0 | 100.0% | inf | 2/0/0 | 1 | 0 | 0 | LOW | INSUFFICIENT_DATA |
| score_bucket | 80-89 | 5 | 0.5209 | 0.1042 | 40.0% | 1.3749 | 2/3/0 | 3 | 1 | 1 | LOW | INSUFFICIENT_DATA |
| score_bucket | 90-100 | 6 | -4.0366 | -0.6728 | 0.0% | 0.0 | 0/6/0 | 4 | 0 | 2 | LOW | INSUFFICIENT_DATA |

## 7. Session/Market/Direction Analysis

### Direction

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| direction | short | 21 | -9.8004 | -0.4667 | 14.2857% | 0.3296 | 3/18/0 | 7 | 2 | 12 | MEDIUM | WATCH |
| direction | long | 20 | 7.225 | 0.3613 | 55.0% | 1.872 | 11/9/0 | 6 | 5 | 8 | MEDIUM | WATCH |

### Session

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| session | LONDON | 14 | 3.084 | 0.2203 | 42.8571% | 1.5257 | 6/8/0 | 6 | 3 | 5 | LOW | INSUFFICIENT_DATA |
| session | OVERLAP | 14 | -0.2511 | -0.0179 | 28.5714% | 0.9688 | 4/10/0 | 5 | 3 | 6 | LOW | INSUFFICIENT_DATA |
| session | NEW_YORK | 12 | -6.4083 | -0.534 | 25.0% | 0.288 | 3/9/0 | 2 | 1 | 9 | LOW | INSUFFICIENT_DATA |
| session | ASIA | 1 | 1.0 | 1.0 | 100.0% | inf | 1/0/0 | 0 | 0 | 0 | LOW | INSUFFICIENT_DATA |

### Market Regime

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| market_regime | RANGING | 18 | -4.0123 | -0.2229 | 38.8889% | 0.6171 | 7/11/0 | 6 | 2 | 10 | MEDIUM | WATCH |
| market_regime | TRENDING | 14 | 0.5167 | 0.0369 | 28.5714% | 1.0615 | 4/10/0 | 3 | 4 | 7 | LOW | INSUFFICIENT_DATA |
| market_regime | HIGH_VOLATILITY | 9 | 0.9202 | 0.1022 | 33.3333% | 1.2283 | 3/6/0 | 4 | 1 | 3 | LOW | INSUFFICIENT_DATA |

### Direction + Market Regime + Entry Context

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| direction + market_regime + entry_context | long + TRENDING + BREAKOUT | 5 | 5.9697 | 1.1939 | 60.0% | 5.6439 | 3/2/0 | 1 | 3 | 1 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | short + RANGING + BREAKOUT | 5 | -0.6108 | -0.1222 | 40.0% | 0.7535 | 2/3/0 | 2 | 1 | 2 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | short + HIGH_VOLATILITY + BREAKOUT | 4 | -2.0308 | -0.5077 | 0.0% | 0.0 | 0/4/0 | 3 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | short + RANGING + CHOPPY_RANGE | 4 | -4.0 | -1.0 | 0.0% | 0.0 | 0/4/0 | 0 | 0 | 4 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | long + HIGH_VOLATILITY + BREAKOUT | 3 | -1.0 | -0.3333 | 33.3333% | 0.5 | 1/2/0 | 1 | 0 | 2 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | long + RANGING + BREAKOUT | 3 | 0.6813 | 0.2271 | 66.6667% | 1.6813 | 2/1/0 | 2 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | long + RANGING + CHOPPY_RANGE | 3 | 0.4104 | 0.1368 | 66.6667% | 1.4104 | 2/1/0 | 2 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | short + TRENDING + BREAKOUT | 3 | -2.1098 | -0.7033 | 0.0% | 0.0 | 0/3/0 | 2 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | short + TRENDING + PULLBACK | 3 | -3.0 | -1.0 | 0.0% | 0.0 | 0/3/0 | 0 | 0 | 3 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | long + RANGING + PULLBACK | 2 | 0.5068 | 0.2534 | 50.0% | 1.5068 | 1/1/0 | 0 | 1 | 1 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | long + TRENDING + EXHAUSTION | 2 | 0.6568 | 0.3284 | 50.0% | 1.6568 | 1/1/0 | 0 | 1 | 1 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | long + HIGH_VOLATILITY + PULLBACK | 1 | 1.0 | 1.0 | 100.0% | inf | 1/0/0 | 0 | 0 | 0 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | long + TRENDING + PULLBACK | 1 | -1.0 | -1.0 | 0.0% | 0.0 | 0/1/0 | 0 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | short + HIGH_VOLATILITY + PULLBACK | 1 | 2.951 | 2.951 | 100.0% | inf | 1/0/0 | 0 | 1 | 0 | LOW | INSUFFICIENT_DATA |
| direction + market_regime + entry_context | short + RANGING + EXHAUSTION | 1 | -1.0 | -1.0 | 0.0% | 0.0 | 0/1/0 | 0 | 0 | 1 | LOW | INSUFFICIENT_DATA |

## 8. Symbol Analysis

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| symbol | BNBUSDT | 6 | 0.3667 | 0.0611 | 50.0% | 1.1222 | 3/3/0 | 1 | 2 | 3 | LOW | INSUFFICIENT_DATA |
| symbol | DOGEUSDT | 5 | -1.1368 | -0.2274 | 20.0% | 0.468 | 1/4/0 | 4 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| symbol | ETHUSDT | 5 | 0.1586 | 0.0317 | 40.0% | 1.0728 | 2/3/0 | 2 | 1 | 2 | LOW | INSUFFICIENT_DATA |
| symbol | SOLUSDT | 4 | -2.0 | -0.5 | 25.0% | 0.3333 | 1/3/0 | 1 | 0 | 3 | LOW | INSUFFICIENT_DATA |
| symbol | XRPUSDT | 4 | -2.5873 | -0.6468 | 0.0% | 0.0 | 0/4/0 | 3 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| symbol | AVAXUSDT | 3 | 0.9172 | 0.3057 | 66.6667% | 1.9172 | 2/1/0 | 1 | 1 | 1 | LOW | INSUFFICIENT_DATA |
| symbol | BTCUSDT | 3 | 4.2552 | 1.4184 | 66.6667% | 5.2552 | 2/1/0 | 1 | 1 | 1 | LOW | INSUFFICIENT_DATA |
| symbol | APEUSDT | 1 | -1.0 | -1.0 | 0.0% | 0.0 | 0/1/0 | 0 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| symbol | ATOMUSDT | 1 | -1.0 | -1.0 | 0.0% | 0.0 | 0/1/0 | 0 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| symbol | DOTUSDT | 1 | 1.5 | 1.5 | 100.0% | inf | 1/0/0 | 0 | 1 | 0 | LOW | INSUFFICIENT_DATA |
| symbol | ETCUSDT | 1 | -1.0 | -1.0 | 0.0% | 0.0 | 0/1/0 | 0 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| symbol | FTMUSDT | 1 | 1.0 | 1.0 | 100.0% | inf | 1/0/0 | 0 | 0 | 0 | LOW | INSUFFICIENT_DATA |
| symbol | ICPUSDT | 1 | -1.0 | -1.0 | 0.0% | 0.0 | 0/1/0 | 0 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| symbol | INJUSDT | 1 | 2.951 | 2.951 | 100.0% | inf | 1/0/0 | 0 | 1 | 0 | LOW | INSUFFICIENT_DATA |
| symbol | SANDUSDT | 1 | -1.0 | -1.0 | 0.0% | 0.0 | 0/1/0 | 0 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| symbol | SUIUSDT | 1 | -1.0 | -1.0 | 0.0% | 0.0 | 0/1/0 | 0 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| symbol | TRXUSDT | 1 | -1.0 | -1.0 | 0.0% | 0.0 | 0/1/0 | 0 | 0 | 1 | LOW | INSUFFICIENT_DATA |
| symbol | UNIUSDT | 1 | -1.0 | -1.0 | 0.0% | 0.0 | 0/1/0 | 0 | 0 | 1 | LOW | INSUFFICIENT_DATA |

## 9. Setup Type Analysis

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| setup_type | MAIN_SIGNAL | 23 | 1.8698 | 0.0813 | 39.1304% | 1.1336 | 9/14/0 | 3 | 5 | 14 | MEDIUM | WATCH |
| setup_type | SECONDARY_SIGNAL | 18 | -4.4452 | -0.247 | 27.7778% | 0.5007 | 5/13/0 | 10 | 2 | 6 | MEDIUM | WATCH |

## 10. Actionable Decisions

### Prioritize Candidates

_No rows._

### Avoid Candidates

_No rows._

### Watchlist

| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| direction | short | 21 | -9.8004 | -0.4667 | 14.2857% | 0.3296 | 3/18/0 | 7 | 2 | 12 | MEDIUM | WATCH |
| direction | long | 20 | 7.225 | 0.3613 | 55.0% | 1.872 | 11/9/0 | 6 | 5 | 8 | MEDIUM | WATCH |
| nearest_distance_to_liquidity_atr_bucket | 1-2 | 20 | -6.2266 | -0.3113 | 25.0% | 0.472 | 5/15/0 | 8 | 2 | 10 | MEDIUM | WATCH |
| direction + setup_type | long + MAIN_SIGNAL | 15 | 5.9188 | 0.3946 | 53.3333% | 1.8455 | 8/7/0 | 3 | 4 | 7 | MEDIUM | WATCH |
| directional_distance_to_liquidity_atr_bucket | 2-3 | 19 | -5.311 | -0.2795 | 26.3158% | 0.6002 | 5/14/0 | 2 | 4 | 13 | MEDIUM | WATCH |
| nearest_distance_to_liquidity_atr_bucket | 0.5-1 | 15 | 5.1977 | 0.3465 | 46.6667% | 1.7041 | 7/8/0 | 3 | 4 | 7 | MEDIUM | WATCH |
| liquidity_sweep | none | 18 | -4.4452 | -0.247 | 27.7778% | 0.5007 | 5/13/0 | 10 | 2 | 6 | MEDIUM | WATCH |
| setup_type | SECONDARY_SIGNAL | 18 | -4.4452 | -0.247 | 27.7778% | 0.5007 | 5/13/0 | 10 | 2 | 6 | MEDIUM | WATCH |
| trend_4h | bearish | 25 | -4.1466 | -0.1659 | 36.0% | 0.7157 | 9/16/0 | 6 | 5 | 13 | MEDIUM | WATCH |
| market_regime | RANGING | 18 | -4.0123 | -0.2229 | 38.8889% | 0.6171 | 7/11/0 | 6 | 2 | 10 | MEDIUM | WATCH |

## 11. What NOT to change yet

- No cambiar contextos con n < 15 aunque parezcan extremos: muestra insuficiente.
- No mezclar open trades con métricas cerradas; están separados en el JSON.
- No priorizar todavía edges positivos con baja muestra; mantenerlos como hipótesis.
- No bloquear todavía contextos negativos de baja muestra salvo que otro sistema independiente los confirme.

## 12. Next experiments

- Comparar los próximos 7 días contra este baseline antes de promover cambios productivos.
