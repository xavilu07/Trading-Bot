# quality_score_failed Deep Dive

Generated at: 2026-06-22T16:00:12+00:00
Mode: offline analysis only. No strategy, scheduler, Telegram, filters or production behavior changed.

## 1. Exact origin

File: `src/trading_signals/domain/strategies/liquidity_sweep_mtf_v1.py`

`quality_score_failed` is generated immediately after the strategy calculates the final score with penalties/bonuses.

### Internal conditions
- `score` starts from `entry.setup_score`.
- Before this check, score is modified by penalties such as timeframe alignment, range market structure, distance to liquidity, distance extreme, secondary setup failure, plus capped secondary confluence bonus.
- `effective_setup_score_threshold = settings.setup_score_threshold + 10` during ASIA, otherwise `settings.setup_score_threshold`.
- If `score >= effective_setup_score_threshold`, the strategy appends `quality_score`.
- If `score < effective_setup_score_threshold`, the strategy appends `quality_score_failed`.

### Hard-veto behavior
`quality_score_failed` is included in the hard-failure set together with volatility/body/late-entry/pullback gates. When present, the strategy skips all primary, secondary, and fallback directional signal branches.

## 2. Source counts

| Source | Count |
|---|---:|
| shadow_signals | 34 |
| scheduler_log_lines | 637 |
| scheduler_log_json_events | 565 |
| signals_log | 6 |
| candidates_rejected | 6 |
| paper_rejection_context | 0 |
| paper_closed_with_target | 0 |

## 3. Breakdowns

### symbol

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| DOGEUSDT | 8 | 59.6875 | 0 | 0.0% | 0.0 | 0.0 |
| XRPUSDT | 7 | 58.3929 | 0 | 0.0% | 0.0 | 0.0 |
| AVAXUSDT | 3 | 70.8333 | 0 | 0.0% | 0.0 | 0.0 |
| SOLUSDT | 3 | 72.0833 | 0 | 0.0% | 0.0 | 0.0 |
| DOTUSDT | 2 | 66.25 | 0 | 0.0% | 0.0 | 0.0 |
| AAVEUSDT | 2 | 72.5 | 0 | 0.0% | 0.0 | 0.0 |
| SEIUSDT | 2 | 68.75 | 0 | 0.0% | 0.0 | 0.0 |
| ETHUSDT | 2 | 67.5 | 0 | 0.0% | 0.0 | 0.0 |
| ATOMUSDT | 1 | 71.25 | 0 | 0.0% | 0.0 | 0.0 |
| BNBUSDT | 1 | 70.0 | 0 | 0.0% | 0.0 | 0.0 |
| BTCUSDT | 1 | 73.75 | 0 | 0.0% | 0.0 | 0.0 |
| TRXUSDT | 1 | 68.75 | 0 | 0.0% | 0.0 | 0.0 |

### direction

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| long | 28 | 69.8214 | 0 | 0.0% | 0.0 | 0.0 |
| short | 12 | 56.25 | 0 | 0.0% | 0.0 | 0.0 |

### setup_type

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 34 | 70.2941 | 0 | 0.0% | 0.0 | 0.0 |
| NO_SIGNAL | 6 | 40.0 | 0 | 0.0% | 0.0 | 0.0 |

### market_regime

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| HIGH_VOLATILITY | 33 | 65.0758 | 0 | 0.0% | 0.0 | 0.0 |
| RANGING | 7 | 68.9286 | 0 | 0.0% | 0.0 | 0.0 |

### session

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 40 | 65.75 | 0 | 0.0% | 0.0 | 0.0 |

### entry_context

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 34 | 70.2941 | 0 | 0.0% | 0.0 | 0.0 |
| EXHAUSTION | 6 | 40.0 | 0 | 0.0% | 0.0 | 0.0 |

### trade_location

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| UNKNOWN | 40 | 65.75 | 0 | 0.0% | 0.0 | 0.0 |

### score_bucket

| Value | Count | Avg score | Closed | WR | PF | Total R |
|---|---:|---:|---:|---:|---:|---:|
| 70-79 | 18 | 73.1944 | 0 | 0.0% | 0.0 | 0.0 |
| 60-69 | 16 | 67.0312 | 0 | 0.0% | 0.0 | 0.0 |
| <60 | 6 | 40.0 | 0 | 0.0% | 0.0 | 0.0 |

## 4. Internal failed conditions from `signals_log`

| Condition | Count |
|---|---:|
| setup_score | 6 |
| short_primary_sweep | 6 |
| short_secondary_bos | 6 |
| short_secondary_volume | 6 |
| short_secondary_structure | 6 |
| short_secondary_score | 6 |

## 5. Co-occurring reasons

| Reason | Count |
|---|---:|
| market_structure_range_penalty | 40 |
| timeframe_alignment_penalty | 21 |
| distance_to_liquidity_penalty | 19 |
| market_structure_range_penalty:10 | 6 |
| distance_to_liquidity_penalty:10 | 6 |
| secondary_confluence_bonus:+15 | 6 |

## 6. Severe cases

- Score >= 70 blocked: 18
- Score >= 80 blocked: 0
- Score >= 90 blocked: 0
- RR valid but blocked: 0
- Trend aligned but blocked: 40
- Liquidity distance passed but blocked: 34
- Directional confluence passed but blocked: 0

### Highest-score examples

| Symbol | Direction | Score | Setup | Session | Regime | Context | Location | Reasons |
|---|---|---:|---|---|---|---|---|---|
| DOGEUSDT | long | 76.25 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | distance_to_liquidity_penalty, market_structure_range_penalty, quality_score_failed |
| SOLUSDT | long | 75.0 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | market_structure_range_penalty, quality_score_failed, timeframe_alignment_penalty |
| XRPUSDT | long | 75.0 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | market_structure_range_penalty, quality_score_failed, timeframe_alignment_penalty |
| AVAXUSDT | long | 75.0 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | market_structure_range_penalty, quality_score_failed, timeframe_alignment_penalty |
| SOLUSDT | long | 75.0 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | market_structure_range_penalty, quality_score_failed, timeframe_alignment_penalty |
| XRPUSDT | long | 75.0 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | market_structure_range_penalty, quality_score_failed, timeframe_alignment_penalty |
| BTCUSDT | long | 73.75 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | distance_to_liquidity_penalty, market_structure_range_penalty, quality_score_failed |
| ARBUSDT | short | 73.75 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | distance_to_liquidity_penalty, market_structure_range_penalty, quality_score_failed |
| AAVEUSDT | short | 73.75 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | distance_to_liquidity_penalty, market_structure_range_penalty, quality_score_failed |
| NEARUSDT | short | 73.75 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | distance_to_liquidity_penalty, market_structure_range_penalty, quality_score_failed |
| XRPUSDT | short | 72.5 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | distance_to_liquidity_penalty, market_structure_range_penalty, quality_score_failed |
| DOGEUSDT | short | 72.5 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | distance_to_liquidity_penalty, market_structure_range_penalty, quality_score_failed |
| ATOMUSDT | long | 71.25 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | market_structure_range_penalty, quality_score_failed, timeframe_alignment_penalty |
| AAVEUSDT | long | 71.25 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | market_structure_range_penalty, quality_score_failed, timeframe_alignment_penalty |
| SEIUSDT | long | 71.25 | UNKNOWN | UNKNOWN | HIGH_VOLATILITY | UNKNOWN | UNKNOWN | market_structure_range_penalty, quality_score_failed, timeframe_alignment_penalty |

## 7. Paper evidence

### Target rows with closed paper outcome

- Closed trades/candidates with target: 0
- WR: 0.0%
- PF: 0.0
- Total R: 0.0
- Avg R: 0.0

### Baseline all closed paper trades

- Closed trades: 41
- WR: 34.1463%
- PF: 0.8876
- Total R: -2.5754
- Avg R: -0.0628

### Best similar contexts

| Context | Closed | WR | PF | Total R | Avg R |
|---|---:|---:|---:|---:|---:|
| no_data | 0 | 0 | 0 | 0 | 0 |

### Worst similar contexts

| Context | Closed | WR | PF | Total R | Avg R |
|---|---:|---:|---:|---:|---:|
| no_data | 0 | 0 | 0 | 0 | 0 |

## 8. Data gaps

- No target records found in data/paper_trading/trades.csv.
- No closed paper outcomes exist for target rows; outcome comparison is weak.

## 9. Conclusion

- Evidence classification: INSUFFICIENT_DATA
- Recommended action: datos insuficientes
- Rationale: Hay pocos resultados paper cerrados asociados a este veto; no conviene relajar todavía.

Allowed action labels considered: mantener como hard veto, convertir parcialmente en penalty, relajar solo por contexto, crear shadow relaxation, datos insuficientes.
