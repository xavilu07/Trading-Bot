# secondary_setup_requirements_failed Deep Dive

Generated at: 2026-06-22T14:47:37+00:00
Mode: offline analysis only. No strategy, scheduler, Telegram, filters or production behavior changed.

## 1. Exact origin

File: `src/trading_signals/domain/strategies/liquidity_sweep_mtf_v1.py`

The veto is generated when a candidate has no primary liquidity sweep and does not satisfy all secondary setup requirements.

### Internal conditions
- `entry.liquidity_sweep == 'none'` is required for secondary setup evaluation.
- `secondary_trend_aligned`: entry trend equals higher timeframe trend and is bullish or bearish.
- `break_of_structure in {'bullish_bos', 'bearish_bos'}`.
- `secondary_volume_favorable`: volume_ratio >= 1.2.
- `secondary_rsi_aligned`: long requires RSI >= 50; short requires RSI <= 50.
- `secondary_nearest_liquidity_valid`: nearest_distance <= max_distance_to_liquidity_atr.
- `secondary_has_structure`: market_structure is not range OR BOS is present.
- `session != 'ASIA'`.
- `score >= setup_score_threshold + 15`, plus +10 more during ASIA.
- If `liquidity_sweep == 'none'` and these combined requirements are not met, the strategy appends `secondary_setup_requirements_failed`, applies `secondary_setup_requirements_failed:20`, and subtracts 20 score points.

### Hard-veto behavior
With `RELAXED_STRATEGY_GATES_ENABLED=false`, any `secondary_setup_requirements_failed` in failed filters sets `has_hard_failures=True`, so the candidate cannot become a real LONG/SHORT even if other modules score well.

## 2. Source counts

| Source | Count |
|---|---:|
| shadow_signals | 43 |
| scheduler_log_lines | 282 |
| scheduler_log_json_events | 124 |
| signals_log | 22 |
| candidates_rejected | 22 |
| paper_rejection_context | 11 |
| paper_closed_with_target | 7 |

## 3. Breakdowns

### symbol

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 13 | 71.25 | 0 | 0.0% | 0.0 | 0.0 |
| ETHUSDT | 10 | 73.375 | 1 | 0.0% | 0.0 | -0.1795 |
| DOGEUSDT | 9 | 80.4167 | 3 | 0.0% | 0.0 | -1.8513 |
| BNBUSDT | 7 | 69.4643 | 1 | 100.0% | inf | 1.5 |
| AVAXUSDT | 7 | 71.4286 | 1 | 100.0% | inf | 0.4104 |
| SOLUSDT | 6 | 73.3333 | 0 | 0.0% | 0.0 | 0.0 |
| XRPUSDT | 4 | 72.1875 | 1 | 0.0% | 0.0 | -0.4775 |
| UNIUSDT | 2 | 77.5 | 0 | 0.0% | 0.0 | 0.0 |
| ALGOUSDT | 2 | 78.75 | 0 | 0.0% | 0.0 | 0.0 |
| MANAUSDT | 2 | 78.125 | 0 | 0.0% | 0.0 | 0.0 |
| TRXUSDT | 1 | 78.75 | 0 | 0.0% | 0.0 | 0.0 |
| BCHUSDT | 1 | 86.25 | 0 | 0.0% | 0.0 | 0.0 |

### direction

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| long | 45 | 75.6944 | 1 | 100.0% | inf | 0.4104 |
| short | 31 | 73.1855 | 6 | 16.6667% | 0.598 | -1.0083 |

### setup_type

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 43 | 79.6512 | 0 | 0.0% | 0.0 | 0.0 |
| SECONDARY_SIGNAL | 21 | 71.1905 | 7 | 28.5714% | 0.7616 | -0.5979 |
| NO_SIGNAL | 12 | 62.9167 | 0 | 0.0% | 0.0 | 0.0 |

### market_regime

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| HIGH_VOLATILITY | 49 | 76.2755 | 4 | 0.0% | 0.0 | -2.0308 |
| RANGING | 17 | 66.9118 | 3 | 66.6667% | 4.0008 | 1.4329 |
| TRENDING | 10 | 80.0 | 0 | 0.0% | 0.0 | 0.0 |

### session

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 65 | 74.0 | 0 | 0.0% | 0.0 | 0.0 |
| LONDON | 8 | 75.0 | 5 | 20.0% | 0.8034 | -0.367 |
| NEW_YORK | 2 | 82.5 | 1 | 100.0% | inf | 0.4104 |
| OVERLAP | 1 | 100.0 | 1 | 0.0% | 0.0 | -0.6413 |

### entry_context

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 43 | 79.6512 | 0 | 0.0% | 0.0 | 0.0 |
| BREAKOUT | 18 | 70.2778 | 6 | 16.6667% | 0.598 | -1.0083 |
| EXHAUSTION | 7 | 64.2857 | 0 | 0.0% | 0.0 | 0.0 |
| CHOPPY_RANGE | 7 | 70.0 | 1 | 100.0% | inf | 0.4104 |
| IMPULSE | 1 | 45.0 | 0 | 0.0% | 0.0 | 0.0 |

### trade_location

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 65 | 74.0 | 0 | 0.0% | 0.0 | 0.0 |
| mid_range | 5 | 77.0 | 2 | 0.0% | 0.0 | -1.21 |
| discount_zone | 3 | 78.3333 | 3 | 0.0% | 0.0 | -1.2983 |
| near_support | 2 | 82.5 | 1 | 100.0% | inf | 1.5 |
| premium_zone | 1 | 80.0 | 1 | 100.0% | inf | 0.4104 |

### score_bucket

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| 70-79 | 32 | 76.4844 | 0 | 0.0% | 0.0 | 0.0 |
| 80-89 | 23 | 82.8804 | 4 | 50.0% | 4.9047 | 1.5209 |
| <60 | 10 | 51.0 | 1 | 0.0% | 0.0 | -0.4775 |
| 60-69 | 8 | 65.1562 | 0 | 0.0% | 0.0 | 0.0 |
| 90+ | 3 | 96.6667 | 2 | 0.0% | 0.0 | -1.6413 |

## 4. Internal failed conditions from `signals_log`

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

## 5. Co-occurring reasons

| Reason | Count |
|---|---:|
| directional_confluence_failed | 76 |
| market_structure_range_penalty | 59 |
| distance_to_liquidity_penalty | 23 |
| market_structure_range_penalty:10 | 22 |
| against_htf | 18 |
| distance_to_liquidity_penalty:10 | 12 |
| secondary_confluence_bonus:+15 | 10 |
| None | 7 |
| secondary_confluence_bonus:+30 | 7 |
| dirty_sideways_market | 7 |
| secondary_confluence_bonus:+25 | 6 |
| low_volume | 3 |

## 6. Severe cases

- Score >= 70 blocked: 58
- Score >= 80 blocked: 26
- Score >= 90 blocked: 3
- RR valid but blocked: 11
- Trend aligned but blocked: 76
- Directional confluence passed but blocked: 0

### Highest-score examples

| Symbol | Direction | Score | Setup | Session | Regime | Context | Location | Reasons |
|---|---|---:|---|---|---|---|---|---|
| DOGEUSDT | short | 100.0 | SECONDARY_SIGNAL | OVERLAP | HIGH_VOLATILITY | BREAKOUT | discount_zone | directional_confluence_failed, secondary_setup_requirements_failed |
| DOGEUSDT | short | 100.0 | SECONDARY_SIGNAL | LONDON | HIGH_VOLATILITY | BREAKOUT | mid_range | directional_confluence_failed, secondary_setup_requirements_failed |
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
| BTCUSDT | long | 82.5 | UNKNOWN | UNKNOWN | RANGING | UNKNOWN | UNKNOWN | directional_confluence_failed, market_structure_range_penalty, secondary_setup_requirements_failed |

## 7. Paper evidence

### Target rows with closed paper outcome

- Closed trades/candidates with target: 7
- WR: 28.5714%
- PF: 0.7616
- Total R: -0.5979
- Avg R: -0.0854

### Baseline all closed paper trades

- Closed trades: 41
- WR: 34.1463%
- PF: 0.8876
- Total R: -2.5754
- Avg R: -0.0628

### Best similar contexts

| Context | Closed | WR | PF | Total R | Avg R |
|---|---:|---:|---:|---:|---:|
| trade_location: near_support | 1 | 100.0% | inf | 1.5 | 1.5 |
| market_regime: RANGING | 3 | 66.6667% | 4.0008 | 1.4329 | 0.4776 |
| session+market_regime: LONDON + RANGING | 2 | 50.0% | 3.1414 | 1.0225 | 0.5112 |
| direction: long | 1 | 100.0% | inf | 0.4104 | 0.4104 |
| session: NEW_YORK | 1 | 100.0% | inf | 0.4104 | 0.4104 |
| entry_context: CHOPPY_RANGE | 1 | 100.0% | inf | 0.4104 | 0.4104 |
| trade_location: premium_zone | 1 | 100.0% | inf | 0.4104 | 0.4104 |
| direction+session: long + NEW_YORK | 1 | 100.0% | inf | 0.4104 | 0.4104 |
| direction+entry_context: long + CHOPPY_RANGE | 1 | 100.0% | inf | 0.4104 | 0.4104 |
| session+market_regime: NEW_YORK + RANGING | 1 | 100.0% | inf | 0.4104 | 0.4104 |

### Worst similar contexts

| Context | Closed | WR | PF | Total R | Avg R |
|---|---:|---:|---:|---:|---:|
| market_regime: HIGH_VOLATILITY | 4 | 0.0% | 0.0 | -2.0308 | -0.5077 |
| session+market_regime: LONDON + HIGH_VOLATILITY | 3 | 0.0% | 0.0 | -1.3895 | -0.4632 |
| trade_location: discount_zone | 3 | 0.0% | 0.0 | -1.2983 | -0.4328 |
| trade_location: mid_range | 2 | 0.0% | 0.0 | -1.21 | -0.605 |
| direction: short | 6 | 16.6667% | 0.598 | -1.0083 | -0.1681 |
| entry_context: BREAKOUT | 6 | 16.6667% | 0.598 | -1.0083 | -0.1681 |
| direction+entry_context: short + BREAKOUT | 6 | 16.6667% | 0.598 | -1.0083 | -0.1681 |
| session: OVERLAP | 1 | 0.0% | 0.0 | -0.6413 | -0.6413 |
| direction+session: short + OVERLAP | 1 | 0.0% | 0.0 | -0.6413 | -0.6413 |
| session+market_regime: OVERLAP + HIGH_VOLATILITY | 1 | 0.0% | 0.0 | -0.6413 | -0.6413 |

## 8. Data gaps

- No major data gaps detected in local files.

## 9. Conclusion

- Evidence classification: INSUFFICIENT_DATA
- Recommended action: datos insuficientes
- Rationale: Hay pocos resultados paper cerrados asociados al veto; no conviene relajar ni endurecer con esta muestra.

Allowed action labels considered: mantener como hard veto, convertir en penalty, relajar solo por contexto, mantener pero crear shadow relaxation, datos insuficientes.
