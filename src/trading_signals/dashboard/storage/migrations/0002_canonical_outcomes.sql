CREATE TABLE outcome_policies (
    policy_version TEXT PRIMARY KEY,
    engine_version TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    horizon_candles INTEGER NOT NULL CHECK (horizon_candles > 0),
    entry_activation_policy TEXT NOT NULL CHECK (
        entry_activation_policy IN (
            'REQUIRE_POST_DECISION_TOUCH',
            'ASSUME_FILLED_AT_DECISION'
        )
    ),
    collision_policy TEXT NOT NULL CHECK (
        collision_policy IN (
            'AMBIGUOUS',
            'CONSERVATIVE_STOP_FIRST',
            'OPTIMISTIC_TARGET_FIRST'
        )
    ),
    require_contiguous_candles INTEGER NOT NULL CHECK (
        require_contiguous_candles IN (0, 1)
    ),
    closed_candles_only INTEGER NOT NULL CHECK (closed_candles_only IN (0, 1)),
    policy_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE market_data_sources (
    market_data_fingerprint TEXT PRIMARY KEY CHECK (
        length(market_data_fingerprint) = 64
    ),
    logical_source_name TEXT NOT NULL,
    source_format TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    coverage_start TEXT,
    coverage_end TEXT,
    candles_count INTEGER NOT NULL CHECK (candles_count >= 0),
    data_quality TEXT NOT NULL CHECK (
        data_quality IN (
            'COMPLETE',
            'PARTIAL',
            'GAP',
            'CONFLICT',
            'NO_DATA',
            'NON_CANONICAL'
        )
    ),
    source_reference TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    registered_at TEXT NOT NULL
);

CREATE TABLE signal_outcomes (
    outcome_id TEXT PRIMARY KEY,
    signal_projection_key TEXT NOT NULL,
    signal_id TEXT,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    timeframe TEXT NOT NULL,
    entry_timestamp TEXT NOT NULL,
    evaluation_start TEXT,
    evaluation_end TEXT,
    entry_price REAL CHECK (entry_price IS NULL OR entry_price > 0),
    stop_price REAL CHECK (stop_price IS NULL OR stop_price > 0),
    target_price REAL CHECK (target_price IS NULL OR target_price > 0),
    candles_expected INTEGER NOT NULL CHECK (candles_expected > 0),
    candles_observed INTEGER NOT NULL CHECK (candles_observed >= 0),
    first_stop_touch_at TEXT,
    first_target_touch_at TEXT,
    terminal_status TEXT NOT NULL CHECK (
        terminal_status IN (
            'WIN',
            'LOSS',
            'EXPIRED',
            'OPEN',
            'AMBIGUOUS',
            'INVALID',
            'NO_MARKET_DATA',
            'NON_CANONICAL'
        )
    ),
    terminal_timestamp TEXT,
    terminal_price REAL,
    ambiguity_reason TEXT,
    data_quality TEXT NOT NULL CHECK (
        data_quality IN (
            'COMPLETE',
            'PARTIAL',
            'GAP',
            'CONFLICT',
            'NO_DATA',
            'NON_CANONICAL'
        )
    ),
    policy_version TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    market_data_fingerprint TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL CHECK (length(source_fingerprint) = 64),
    git_commit_sha TEXT,
    deployment_id TEXT,
    config_hash TEXT,
    selected_engine TEXT,
    strategy_version TEXT,
    signal_policy_version TEXT,
    experiment_id TEXT,
    computed_at TEXT NOT NULL,
    UNIQUE (
        signal_projection_key,
        policy_version,
        market_data_fingerprint
    ),
    FOREIGN KEY (signal_projection_key)
        REFERENCES signals(projection_key),
    FOREIGN KEY (policy_version)
        REFERENCES outcome_policies(policy_version),
    FOREIGN KEY (market_data_fingerprint)
        REFERENCES market_data_sources(market_data_fingerprint)
);

CREATE TABLE outcome_evidence (
    evidence_id TEXT PRIMARY KEY,
    outcome_id TEXT NOT NULL,
    candle_index INTEGER NOT NULL CHECK (candle_index > 0),
    candle_open_at TEXT NOT NULL,
    candle_close_at TEXT NOT NULL,
    open_price REAL NOT NULL CHECK (open_price > 0),
    high_price REAL NOT NULL CHECK (high_price > 0),
    low_price REAL NOT NULL CHECK (low_price > 0),
    close_price REAL NOT NULL CHECK (close_price > 0),
    entry_touched INTEGER NOT NULL CHECK (entry_touched IN (0, 1)),
    stop_touched INTEGER NOT NULL CHECK (stop_touched IN (0, 1)),
    target_touched INTEGER NOT NULL CHECK (target_touched IN (0, 1)),
    evidence_json TEXT NOT NULL,
    CHECK (low_price <= open_price),
    CHECK (low_price <= close_price),
    CHECK (high_price >= open_price),
    CHECK (high_price >= close_price),
    CHECK (low_price <= high_price),
    UNIQUE (outcome_id, candle_open_at),
    FOREIGN KEY (outcome_id)
        REFERENCES signal_outcomes(outcome_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_signal_outcomes_status
    ON signal_outcomes(terminal_status, terminal_timestamp);
CREATE INDEX idx_signal_outcomes_entry_timestamp
    ON signal_outcomes(entry_timestamp DESC);
CREATE INDEX idx_signal_outcomes_symbol
    ON signal_outcomes(symbol, timeframe, entry_timestamp DESC);
CREATE INDEX idx_signal_outcomes_strategy
    ON signal_outcomes(
        selected_engine,
        strategy_version,
        signal_policy_version,
        entry_timestamp DESC
    );
CREATE INDEX idx_signal_outcomes_policy
    ON signal_outcomes(policy_version, market_data_fingerprint);
CREATE INDEX idx_outcome_evidence_outcome
    ON outcome_evidence(outcome_id, candle_index);
