# Strategy Validation Suite

- Generated at: 2026-05-28T16:11:05+00:00
- Validation status: DANGEROUS
- Records analyzed: 253
- Closed records: 55
- Confidence: MEDIUM

## Full History

- PF: 0.5779
- WR: 25.45%
- AvgR: -0.2832
- Max DD: -19.1323

## Rolling Validation

- Windows: 1
- PF stability: 0.0
- WR stability: 0.0
- AvgR stability: 0.0

## Delayed Execution

- Delayed records: 52
- Skipped early resolution: 3
- Delayed PF: 0.5265
- Delayed WR: 25.0%

## Validation Matrix

- lookahead_bias_detection: SAFE | future_dependency_suspicion_rate=0.0 | 0 suspicious records
- recursive_recalculation_consistency: SAFE | setup_drift_rate=0.0 | 0 duplicate keys changed setup/score
- rolling_window_validation: SAFE | avgR_drift_vs_full_history=0.0 | 1 rolling windows
- candle_close_dependency_detection: SAFE | pre_close_signal_rate=0.0 | 0 records opened before candle close
- signal_timestamp_consistency: SAFE | timestamp_mismatch_rate=0.0 | 0 closed_at before opened_at
- delayed_entry_simulation: SAFE | delayed_avgR_drift=0.0346 | early_resolution_rate=0.0545
- indicator_recalculation_drift: SAFE | indicator_or_score_drift_rate=0.0 | 0 duplicate keys with indicator/score drift
- rolling_pf_stability: SAFE | pf_stddev=0.0 | 
- rolling_wr_stability: SAFE | wr_stddev=0.0 | 
- overfit_context_detection: DANGEROUS | unstable_contexts=10 | setup_type=UNKNOWN; session=UNKNOWN; trade_location=UNKNOWN; trade_location=premium_zone; direction=short

## Recommended Actions

- investigate_immediately:overfit_context_detection:setup_type=UNKNOWN; session=UNKNOWN; trade_location=UNKNOWN; trade_location=premium_zone; direction=short
