ALTER TABLE signal_outcomes
    ADD COLUMN entry_activated INTEGER CHECK (
        entry_activated IS NULL OR entry_activated IN (0, 1)
    );
ALTER TABLE signal_outcomes ADD COLUMN entry_activated_at TEXT;
ALTER TABLE signal_outcomes ADD COLUMN entry_activation_candle_open TEXT;
ALTER TABLE signal_outcomes ADD COLUMN entry_activation_evidence_id TEXT;
ALTER TABLE signal_outcomes
    ADD COLUMN candles_until_entry INTEGER CHECK (
        candles_until_entry IS NULL OR candles_until_entry > 0
    );
ALTER TABLE signal_outcomes
    ADD COLUMN candles_after_entry INTEGER CHECK (
        candles_after_entry IS NULL OR candles_after_entry >= 0
    );
ALTER TABLE signal_outcomes
    ADD COLUMN entry_lifecycle_status TEXT CHECK (
        entry_lifecycle_status IS NULL OR entry_lifecycle_status IN (
            'SIGNAL_OBSERVED',
            'ENTRY_NOT_ACTIVATED',
            'ENTRY_ACTIVATED',
            'RESOLVED_WIN',
            'RESOLVED_LOSS',
            'ACTIVATED_EXPIRED',
            'UNRESOLVED_AMBIGUOUS',
            'INSUFFICIENT_EVIDENCE'
        )
    );
ALTER TABLE signal_outcomes
    ADD COLUMN eligibility_status TEXT CHECK (
        eligibility_status IS NULL OR eligibility_status IN (
            'ELIGIBLE_RESOLVED',
            'ELIGIBLE_ACTIVATED',
            'NOT_ACTIVATED',
            'EXCLUDED_AMBIGUOUS',
            'EXCLUDED_NO_MARKET_DATA',
            'EXCLUDED_CONFLICTING_DATA',
            'EXCLUDED_IDENTITY',
            'EXCLUDED_POLICY_MISMATCH',
            'EXCLUDED_INVALID_LEVELS',
            'EXCLUDED_NON_CANONICAL',
            'EXCLUDED_INCOMPLETE_EVIDENCE'
        )
    );
ALTER TABLE signal_outcomes ADD COLUMN eligibility_reason TEXT;

UPDATE signal_outcomes
SET
    entry_activated = CASE
        WHEN EXISTS (
            SELECT 1 FROM outcome_evidence e
            WHERE e.outcome_id=signal_outcomes.outcome_id
              AND e.entry_touched=1
        ) THEN 1 ELSE 0
    END,
    entry_activation_candle_open = (
        SELECT e.candle_open_at
        FROM outcome_evidence e
        WHERE e.outcome_id=signal_outcomes.outcome_id
          AND e.entry_touched=1
        ORDER BY e.candle_index
        LIMIT 1
    ),
    entry_activation_evidence_id = (
        SELECT e.evidence_id
        FROM outcome_evidence e
        WHERE e.outcome_id=signal_outcomes.outcome_id
          AND e.entry_touched=1
        ORDER BY e.candle_index
        LIMIT 1
    ),
    candles_until_entry = (
        SELECT MIN(e.candle_index)
        FROM outcome_evidence e
        WHERE e.outcome_id=signal_outcomes.outcome_id
          AND e.entry_touched=1
    ),
    candles_after_entry = CASE
        WHEN EXISTS (
            SELECT 1 FROM outcome_evidence e
            WHERE e.outcome_id=signal_outcomes.outcome_id
              AND e.entry_touched=1
        ) THEN candles_observed - (
            SELECT MIN(e.candle_index)
            FROM outcome_evidence e
            WHERE e.outcome_id=signal_outcomes.outcome_id
              AND e.entry_touched=1
        )
        ELSE NULL
    END;

UPDATE signal_outcomes
SET entry_activated_at = (
    SELECT e.candle_open_at
    FROM outcome_evidence e
    WHERE e.evidence_id=signal_outcomes.entry_activation_evidence_id
      AND e.open_price=signal_outcomes.entry_price
);

UPDATE signal_outcomes
SET entry_lifecycle_status = CASE
    WHEN terminal_status='WIN' AND entry_activated=1 THEN 'RESOLVED_WIN'
    WHEN terminal_status='LOSS' AND entry_activated=1 THEN 'RESOLVED_LOSS'
    WHEN terminal_status='EXPIRED' AND entry_activated=1 THEN 'ACTIVATED_EXPIRED'
    WHEN terminal_status='EXPIRED' AND entry_activated=0 THEN 'ENTRY_NOT_ACTIVATED'
    WHEN terminal_status='AMBIGUOUS' THEN 'UNRESOLVED_AMBIGUOUS'
    WHEN terminal_status='OPEN' AND entry_activated=1 THEN 'ENTRY_ACTIVATED'
    WHEN terminal_status='OPEN' THEN 'SIGNAL_OBSERVED'
    ELSE 'INSUFFICIENT_EVIDENCE'
END;

UPDATE signal_outcomes
SET
    eligibility_status = CASE
        WHEN policy_version<>'closed-bars-entry-touch-v1'
          OR engine_version<>'canonical-outcomes.v1'
            THEN 'EXCLUDED_POLICY_MISMATCH'
        WHEN strategy_version IS NULL
          OR lower(strategy_version)='unknown'
            THEN 'EXCLUDED_IDENTITY'
        WHEN entry_price IS NULL OR stop_price IS NULL OR target_price IS NULL
          OR (direction='long' AND NOT (
              stop_price < entry_price AND entry_price < target_price
          ))
          OR (direction='short' AND NOT (
              target_price < entry_price AND entry_price < stop_price
          ))
            THEN 'EXCLUDED_INVALID_LEVELS'
        WHEN length(market_data_fingerprint)<>64
            THEN 'EXCLUDED_CONFLICTING_DATA'
        WHEN data_quality='CONFLICT'
            THEN 'EXCLUDED_CONFLICTING_DATA'
        WHEN data_quality='NON_CANONICAL'
          OR terminal_status='NON_CANONICAL'
            THEN 'EXCLUDED_NON_CANONICAL'
        WHEN terminal_status='AMBIGUOUS'
            THEN 'EXCLUDED_AMBIGUOUS'
        WHEN terminal_status='NO_MARKET_DATA'
          OR data_quality IN ('GAP', 'NO_DATA')
            THEN 'EXCLUDED_NO_MARKET_DATA'
        WHEN data_quality<>'COMPLETE'
            THEN 'EXCLUDED_INCOMPLETE_EVIDENCE'
        WHEN entry_activated=0
            THEN 'NOT_ACTIVATED'
        WHEN terminal_status IN ('WIN', 'LOSS')
            THEN 'ELIGIBLE_RESOLVED'
        WHEN terminal_status='EXPIRED'
            THEN 'ELIGIBLE_ACTIVATED'
        ELSE 'EXCLUDED_INCOMPLETE_EVIDENCE'
    END,
    eligibility_reason = CASE
        WHEN policy_version<>'closed-bars-entry-touch-v1'
          OR engine_version<>'canonical-outcomes.v1'
            THEN 'POLICY_OR_ENGINE_VERSION_MISMATCH'
        WHEN strategy_version IS NULL
          OR lower(strategy_version)='unknown'
            THEN 'STRATEGY_IDENTITY_MISSING'
        WHEN entry_price IS NULL OR stop_price IS NULL OR target_price IS NULL
          OR (direction='long' AND NOT (
              stop_price < entry_price AND entry_price < target_price
          ))
          OR (direction='short' AND NOT (
              target_price < entry_price AND entry_price < stop_price
          ))
            THEN 'SIGNAL_LEVELS_INVALID'
        WHEN length(market_data_fingerprint)<>64
            THEN 'MARKET_FINGERPRINT_INVALID'
        WHEN data_quality='CONFLICT'
            THEN 'MARKET_EVIDENCE_CONFLICT'
        WHEN data_quality='NON_CANONICAL'
          OR terminal_status='NON_CANONICAL'
            THEN 'OUTCOME_NON_CANONICAL'
        WHEN terminal_status='AMBIGUOUS'
            THEN 'OHLC_INTRABAR_ORDER_AMBIGUOUS'
        WHEN terminal_status='NO_MARKET_DATA'
          OR data_quality IN ('GAP', 'NO_DATA')
            THEN 'MARKET_EVIDENCE_INCOMPLETE'
        WHEN data_quality<>'COMPLETE'
            THEN 'EVIDENCE_NOT_COMPLETE'
        WHEN entry_activated=0
            THEN 'ENTRY_NOT_TOUCHED_WITHIN_HORIZON'
        WHEN terminal_status='WIN'
            THEN 'ENTRY_ACTIVATED_TARGET_RESOLVED'
        WHEN terminal_status='LOSS'
            THEN 'ENTRY_ACTIVATED_STOP_RESOLVED'
        WHEN terminal_status='EXPIRED'
            THEN 'ENTRY_ACTIVATED_HORIZON_EXPIRED'
        WHEN terminal_status='OPEN'
            THEN 'OUTCOME_HORIZON_INCOMPLETE'
        ELSE 'TERMINAL_STATUS_NOT_METRIC_ELIGIBLE'
    END;

CREATE TABLE metric_definitions (
    definition_key TEXT PRIMARY KEY,
    definition_version TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    cohort_kind TEXT NOT NULL,
    unit TEXT NOT NULL CHECK (
        unit IN ('COUNT', 'RATE', 'R', 'CANDLES')
    ),
    formula TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    definition_checksum TEXT NOT NULL CHECK (
        length(definition_checksum) = 64
    ),
    created_at TEXT NOT NULL,
    UNIQUE (metric_name, definition_version, cohort_kind)
);

CREATE TABLE metric_runs (
    run_id TEXT PRIMARY KEY,
    metric_definition_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    policy_checksum TEXT NOT NULL CHECK (length(policy_checksum) = 64),
    engine_version TEXT NOT NULL,
    outcome_dataset_fingerprint TEXT NOT NULL CHECK (
        length(outcome_dataset_fingerprint) = 64
    ),
    strategy_scope TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    outcomes_observed INTEGER NOT NULL CHECK (outcomes_observed >= 0),
    signals_observed INTEGER NOT NULL CHECK (signals_observed >= 0),
    status TEXT NOT NULL CHECK (status IN ('COMPLETE', 'FAILED')),
    run_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    UNIQUE (
        metric_definition_version,
        policy_checksum,
        outcome_dataset_fingerprint,
        strategy_scope
    )
);

CREATE TABLE metric_cohorts (
    cohort_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    cohort_name TEXT NOT NULL,
    cohort_fingerprint TEXT NOT NULL CHECK (length(cohort_fingerprint) = 64),
    dimension_name TEXT,
    dimension_value TEXT,
    filters_json TEXT NOT NULL,
    included_statuses_json TEXT NOT NULL,
    excluded_statuses_json TEXT NOT NULL,
    denominator INTEGER NOT NULL CHECK (denominator >= 0),
    period_start TEXT,
    period_end TEXT,
    policy_version TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    strategy_identity TEXT NOT NULL,
    evidence_quality TEXT NOT NULL,
    sample_label TEXT NOT NULL CHECK (
        sample_label IN (
            'ANECDOTAL',
            'INSUFFICIENT',
            'PRELIMINARY',
            'ANALYZABLE'
        )
    ),
    cohort_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (run_id, cohort_name, cohort_fingerprint),
    FOREIGN KEY (run_id) REFERENCES metric_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE metric_values (
    metric_value_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    cohort_id TEXT NOT NULL,
    definition_key TEXT NOT NULL,
    value REAL,
    numerator REAL,
    denominator INTEGER NOT NULL CHECK (denominator >= 0),
    confidence_lower REAL,
    confidence_upper REAL,
    value_json TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    UNIQUE (run_id, cohort_id, definition_key),
    FOREIGN KEY (run_id) REFERENCES metric_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (cohort_id) REFERENCES metric_cohorts(cohort_id) ON DELETE CASCADE,
    FOREIGN KEY (definition_key)
        REFERENCES metric_definitions(definition_key)
);

CREATE TABLE metric_exclusions (
    exclusion_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    outcome_id TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    exclusion_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (run_id, outcome_id, reason_code),
    FOREIGN KEY (run_id) REFERENCES metric_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (outcome_id)
        REFERENCES signal_outcomes(outcome_id) ON DELETE CASCADE
);

CREATE INDEX idx_signal_outcomes_entry_eligibility
    ON signal_outcomes(
        eligibility_status,
        entry_activated,
        entry_timestamp DESC
    );
CREATE INDEX idx_signal_outcomes_lifecycle
    ON signal_outcomes(entry_lifecycle_status, entry_timestamp DESC);
CREATE INDEX idx_metric_runs_policy
    ON metric_runs(policy_version, engine_version, completed_at DESC);
CREATE INDEX idx_metric_runs_dataset
    ON metric_runs(outcome_dataset_fingerprint);
CREATE INDEX idx_metric_cohorts_dimension
    ON metric_cohorts(run_id, dimension_name, dimension_value);
CREATE INDEX idx_metric_cohorts_sample
    ON metric_cohorts(sample_label, denominator DESC);
CREATE INDEX idx_metric_values_definition
    ON metric_values(definition_key, cohort_id);
CREATE INDEX idx_metric_exclusions_reason
    ON metric_exclusions(run_id, reason_code);
