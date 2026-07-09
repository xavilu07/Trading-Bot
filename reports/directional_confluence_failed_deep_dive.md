# directional_confluence_failed Deep Dive

Generated at: 2026-06-22T15:05:11+00:00
Mode: offline analysis only. No strategy, scheduler, Telegram, filters or production behavior changed.

## 1. Exact origin

File: `src/trading_signals/domain/strategies/liquidity_sweep_mtf_v1.py`

The veto is generated in the final fallback branch after primary sweep and secondary setup paths fail.

### Internal conditions
- Primary LONG passes only when entry trend is bullish, liquidity_sweep is bullish_sweep, market_structure is bullish/range, HTF is not bearish unless counter-HTF reversal is allowed, distance is not extreme, range quality is allowed when in range, and ASIA score is >= 85.
- Primary SHORT passes only when entry trend is bearish, liquidity_sweep is bearish_sweep, market_structure is bearish/range, HTF is not bullish, distance is not extreme, range quality is allowed when in range, and ASIA score is >= 85.
- Secondary LONG passes only outside ASIA with entry and HTF bullish, liquidity_sweep none, bullish BOS, volume confirmation, RSI alignment, nearest liquidity valid, structure valid, and score >= secondary threshold.
- Secondary SHORT passes only outside ASIA with entry and HTF bearish, liquidity_sweep none, bearish BOS, volume confirmation, RSI alignment, nearest liquidity valid, structure valid, and score >= secondary threshold.
- If neither primary nor secondary path passes, fallback_direction is inferred from liquidity_sweep or BOS.
- If bullish entry contradicts bearish HTF and counter-HTF reversal is not allowed, the code records higher_timeframe_contradicts_long instead of directional_confluence_failed.
- If bearish entry contradicts bullish HTF, the code records higher_timeframe_contradicts_short instead of directional_confluence_failed.
- `directional_confluence_failed` is appended when no valid primary/secondary path exists, no HTF contradiction-specific reason is selected, and relaxed soft allowance is disabled or unavailable.
- Soft allowance requires relaxed gates enabled, fallback direction present, score >= 80, no HTF contradiction for fallback, no distance_to_liquidity_extreme, and non-ASIA session.

### Interpretation
`directional_confluence_failed` is not a single indicator failure. It is a final aggregate veto meaning the candidate could not satisfy the directional recipe for primary sweep, secondary continuation, or allowed relaxed fallback.

## 2. Source counts

| Source | Count |
|---|---:|
| shadow_signals | 43 |
| scheduler_log_lines | 330 |
| scheduler_log_json_events | 261 |
| signals_log | 22 |
| candidates_rejected | 22 |
| paper_rejection_context | 17 |
| paper_closed_with_target | 13 |

## 3. Breakdowns

### symbol

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 14 | 71.1607 | 1 | 100.0% | inf | 1.0 |
| ETHUSDT | 11 | 70.7955 | 2 | 0.0% | 0.0 | -1.1795 |
| DOGEUSDT | 9 | 80.4167 | 3 | 0.0% | 0.0 | -1.8513 |
| SOLUSDT | 7 | 69.2857 | 1 | 0.0% | 0.0 | -1.0 |
| BNBUSDT | 7 | 69.4643 | 1 | 100.0% | inf | 1.5 |
| AVAXUSDT | 7 | 71.4286 | 1 | 100.0% | inf | 0.4104 |
| XRPUSDT | 5 | 66.75 | 2 | 0.0% | 0.0 | -1.4775 |
| TRXUSDT | 2 | 61.875 | 1 | 0.0% | 0.0 | -1.0 |
| UNIUSDT | 2 | 77.5 | 0 | 0.0% | 0.0 | 0.0 |
| ALGOUSDT | 2 | 78.75 | 0 | 0.0% | 0.0 | 0.0 |
| MANAUSDT | 2 | 78.125 | 0 | 0.0% | 0.0 | 0.0 |
| BCHUSDT | 1 | 86.25 | 0 | 0.0% | 0.0 | 0.0 |

### direction

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| long | 49 | 74.8214 | 5 | 40.0% | 0.4701 | -1.5896 |
| short | 33 | 71.4773 | 8 | 12.5% | 0.3327 | -3.0083 |

### setup_type

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 43 | 79.6512 | 0 | 0.0% | 0.0 | 0.0 |
| SECONDARY_SIGNAL | 21 | 71.1905 | 7 | 28.5714% | 0.7616 | -0.5979 |
| NO_SIGNAL | 12 | 62.9167 | 0 | 0.0% | 0.0 | 0.0 |
| MAIN_SIGNAL | 6 | 58.3333 | 6 | 16.6667% | 0.2 | -4.0 |

### market_regime

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| HIGH_VOLATILITY | 50 | 76.75 | 5 | 0.0% | 0.0 | -3.0308 |
| RANGING | 22 | 63.0682 | 8 | 37.5% | 0.65 | -1.5671 |
| TRENDING | 10 | 80.0 | 0 | 0.0% | 0.0 | 0.0 |

### session

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 65 | 74.0 | 0 | 0.0% | 0.0 | 0.0 |
| LONDON | 11 | 69.0909 | 8 | 25.0% | 0.6465 | -1.367 |
| NEW_YORK | 4 | 77.5 | 3 | 33.3333% | 0.2052 | -1.5896 |
| OVERLAP | 2 | 72.5 | 2 | 0.0% | 0.0 | -1.6413 |

### entry_context

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 43 | 79.6512 | 0 | 0.0% | 0.0 | 0.0 |
| BREAKOUT | 21 | 70.4762 | 9 | 22.2222% | 0.5545 | -2.0083 |
| CHOPPY_RANGE | 9 | 64.4444 | 3 | 33.3333% | 0.2052 | -1.5896 |
| EXHAUSTION | 8 | 61.875 | 1 | 0.0% | 0.0 | -1.0 |
| IMPULSE | 1 | 45.0 | 0 | 0.0% | 0.0 | 0.0 |

### trade_location

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 65 | 74.0 | 0 | 0.0% | 0.0 | 0.0 |
| near_support | 5 | 71.0 | 4 | 25.0% | 0.5 | -1.5 |
| mid_range | 5 | 77.0 | 2 | 0.0% | 0.0 | -1.21 |
| discount_zone | 4 | 76.25 | 4 | 25.0% | 0.7702 | -0.2983 |
| premium_zone | 2 | 62.5 | 2 | 50.0% | 0.4104 | -0.5896 |
| near_resistance | 1 | 45.0 | 1 | 0.0% | 0.0 | -1.0 |

### score_bucket

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| 70-79 | 33 | 76.2879 | 1 | 100.0% | inf | 1.0 |
| 80-89 | 23 | 82.8804 | 4 | 50.0% | 4.9047 | 1.5209 |
| <60 | 14 | 49.2857 | 5 | 0.0% | 0.0 | -4.4775 |
| 60-69 | 8 | 65.1562 | 0 | 0.0% | 0.0 | 0.0 |
| 90+ | 4 | 97.5 | 3 | 0.0% | 0.0 | -2.6413 |

## 4. Setup path split

| Path | Count | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|
| secondary_path_like | 76 | 7 | 28.5714% | 0.7616 | -0.5979 |
| primary_path_like | 6 | 6 | 16.6667% | 0.2 | -4.0 |

## 5. Internal failed conditions from `signals_log`

| Condition | Count |
|---|---:|
| short_primary_sweep | 12 |
| short_secondary_bos | 12 |
| long_primary_trend | 10 |
| long_primary_sweep | 10 |
| long_primary_htf | 10 |
| long_secondary_trend_alignment | 10 |
| long_secondary_rsi | 10 |
| short_secondary_volume | 10 |
| short_secondary_structure | 9 |
| long_secondary_score | 6 |
| long_secondary_volume | 4 |
| short_secondary_score | 2 |

## 6. Co-occurring reasons

| Reason | Count |
|---|---:|
| secondary_setup_requirements_failed | 76 |
| market_structure_range_penalty | 64 |
| distance_to_liquidity_penalty | 27 |
| against_htf | 22 |
| market_structure_range_penalty:10 | 22 |
| distance_to_liquidity_penalty:10 | 12 |
| secondary_confluence_bonus:+15 | 10 |
| dirty_sideways_market | 8 |
| secondary_confluence_bonus:+30 | 7 |
| None | 7 |
| secondary_confluence_bonus:+25 | 6 |
| low_volume | 4 |

## 7. Severe cases

- Score >= 70 blocked: 60
- Score >= 80 blocked: 27
- Score >= 90 blocked: 4
- RR valid but blocked: 17
- Trend aligned but blocked: 82
- Liquidity distance passed but blocked: 71
- Primary path-like blocked: 6
- Secondary path-like blocked: 76

### Highest-score examples

| Symbol | Direction | Score | Setup | Session | Regime | Context | Location | Reasons |
|---|---|---:|---|---|---|---|---|---|
| DOGEUSDT | short | 100.0 | SECONDARY_SIGNAL | OVERLAP | HIGH_VOLATILITY | BREAKOUT | discount_zone | directional_confluence_failed, secondary_setup_requirements_failed |
| DOGEUSDT | short | 100.0 | SECONDARY_SIGNAL | LONDON | HIGH_VOLATILITY | BREAKOUT | mid_range | directional_confluence_failed, secondary_setup_requirements_failed |
| APEUSDT | long | 100.0 | MAIN_SIGNAL | NEW_YORK | HIGH_VOLATILITY | BREAKOUT | near_support | directional_confluence_failed |
| BTCUSDT | long | 90.0 | UNKNOWN | UNKNOWN | TRENDING | UNKNOWN | UNKNOWN | directional_confluence_failed, distance_to_liquidity_extreme, secondary_setup_requirements_failed |
| ETHUSDT | long | 87.5 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | directional_confluence_failed, market_structure_range_penalty, secondary_setup_requirements_failed |
| DOGEUSDT | long | 87.5 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | directional_confluence_failed, market_structure_range_penalty, secondary_setup_requirements_failed |
| ETHUSDT | long | 87.5 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | directional_confluence_failed, market_structure_range_penalty, secondary_setup_requirements_failed |
| SOLUSDT | long | 87.5 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | directional_confluence_failed, market_structure_range_penalty, secondary_setup_requirements_failed |
| BCHUSDT | short | 86.25 | UNKNOWN | UNKNOWN | TRENDING | UNKNOWN | UNKNOWN | directional_confluence_failed, secondary_setup_requirements_failed |
| BTCUSDT | long | 86.25 | UNKNOWN | UNKNOWN | TRENDING | UNKNOWN | UNKNOWN | directional_confluence_failed, distance_to_liquidity_extreme, secondary_setup_requirements_failed |
| MANAUSDT | short | 85.0 | SECONDARY_SIGNAL | NEW_YORK | TRENDING | BREAKOUT | near_support | directional_confluence_failed, distance_to_liquidity_penalty, secondary_setup_requirements_failed |
| RUNEUSDT | long | 83.75 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | directional_confluence_failed, secondary_setup_requirements_failed |
| ARUSDT | short | 83.75 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | directional_confluence_failed, secondary_setup_requirements_failed |
| BTCUSDT | long | 83.75 | UNKNOWN | UNKNOWN | TRENDING | UNKNOWN | UNKNOWN | directional_confluence_failed, distance_to_liquidity_penalty, secondary_setup_requirements_failed |
| XRPUSDT | long | 83.75 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | directional_confluence_failed, market_structure_range_penalty, secondary_setup_requirements_failed |

## 8. Paper evidence

### Target rows with closed paper outcome

- Closed trades/candidates with target: 13
- WR: 23.0769%
- PF: 0.3876
- Total R: -4.5979
- Avg R: -0.3537

### Baseline all closed paper trades

- Closed trades: 41
- WR: 34.1463%
- PF: 0.8876
- Total R: -2.5754
- Avg R: -0.0628

### Best similar contexts

| Context | Closed | WR | PF | Total R | Avg R |
|---|---:|---:|---:|---:|---:|
| session+market_regime: LONDON + RANGING | 5 | 40.0% | 1.0091 | 0.0225 | 0.0045 |
| direction+session: long + LONDON | 2 | 50.0% | 1.0 | 0.0 | 0.0 |
| trade_location: discount_zone | 4 | 25.0% | 0.7702 | -0.2983 | -0.0746 |
| trade_location: premium_zone | 2 | 50.0% | 0.4104 | -0.5896 | -0.2948 |
| direction+session: long + NEW_YORK | 2 | 50.0% | 0.4104 | -0.5896 | -0.2948 |
| direction+entry_context: long + CHOPPY_RANGE | 2 | 50.0% | 0.4104 | -0.5896 | -0.2948 |
| session+market_regime: NEW_YORK + RANGING | 2 | 50.0% | 0.4104 | -0.5896 | -0.2948 |
| setup_type: SECONDARY_SIGNAL | 7 | 28.5714% | 0.7616 | -0.5979 | -0.0854 |
| setup_path: secondary_path_like | 7 | 28.5714% | 0.7616 | -0.5979 | -0.0854 |
| direction+session: short + OVERLAP | 1 | 0.0% | 0.0 | -0.6413 | -0.6413 |

### Worst similar contexts

| Context | Closed | WR | PF | Total R | Avg R |
|---|---:|---:|---:|---:|---:|
| setup_type: MAIN_SIGNAL | 6 | 16.6667% | 0.2 | -4.0 | -0.6667 |
| setup_path: primary_path_like | 6 | 16.6667% | 0.2 | -4.0 | -0.6667 |
| market_regime: HIGH_VOLATILITY | 5 | 0.0% | 0.0 | -3.0308 | -0.6062 |
| direction: short | 8 | 12.5% | 0.3327 | -3.0083 | -0.376 |
| entry_context: BREAKOUT | 9 | 22.2222% | 0.5545 | -2.0083 | -0.2231 |
| session: OVERLAP | 2 | 0.0% | 0.0 | -1.6413 | -0.8206 |
| session: NEW_YORK | 3 | 33.3333% | 0.2052 | -1.5896 | -0.5299 |
| entry_context: CHOPPY_RANGE | 3 | 33.3333% | 0.2052 | -1.5896 | -0.5299 |
| direction: long | 5 | 40.0% | 0.4701 | -1.5896 | -0.3179 |
| market_regime: RANGING | 8 | 37.5% | 0.65 | -1.5671 | -0.1959 |

## 9. Data gaps

- No major data gaps detected in local files.

## 10. Conclusion

- Evidence classification: PROTECTIVE
- Recommended action: mantener como hard veto
- Rationale: Los casos cerrados asociados al veto muestran TotalR -4.5979 y PF 0.3876; la evidencia favorece protección.

Allowed action labels considered: mantener como hard veto, convertir parcialmente en penalty, relajar solo por contexto, crear shadow relaxation, datos insuficientes.
