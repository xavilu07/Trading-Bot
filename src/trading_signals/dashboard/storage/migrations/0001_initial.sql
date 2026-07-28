CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    checksum TEXT NOT NULL
);

CREATE TABLE source_metadata (
    logical_source_name TEXT PRIMARY KEY,
    source_format TEXT NOT NULL,
    source_classification TEXT NOT NULL,
    availability TEXT NOT NULL,
    last_attempt_at TEXT,
    last_success_at TEXT,
    source_observed_at TEXT,
    freshness_status TEXT NOT NULL,
    source_fingerprint TEXT,
    record_count INTEGER CHECK (record_count IS NULL OR record_count >= 0),
    last_error_code TEXT,
    last_error_message TEXT,
    projector_version TEXT NOT NULL
);

CREATE TABLE ingestion_checkpoints (
    logical_source_name TEXT NOT NULL,
    source_identity TEXT NOT NULL,
    source_fingerprint TEXT,
    byte_offset INTEGER CHECK (byte_offset IS NULL OR byte_offset >= 0),
    record_index INTEGER CHECK (record_index IS NULL OR record_index >= 0),
    last_event_id TEXT,
    last_event_timestamp TEXT,
    completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (logical_source_name, source_identity),
    FOREIGN KEY (logical_source_name)
        REFERENCES source_metadata(logical_source_name)
        ON DELETE CASCADE
);

CREATE TABLE system_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    observed_at TEXT NOT NULL,
    component TEXT NOT NULL,
    normalized_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    freshness_status TEXT NOT NULL,
    evidence_reference TEXT NOT NULL,
    git_commit_sha TEXT,
    deployment_id TEXT,
    config_hash TEXT,
    selected_engine TEXT,
    strategy_version TEXT,
    policy_version TEXT,
    experiment_id TEXT,
    payload_json TEXT NOT NULL,
    source_logical_name TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    FOREIGN KEY (source_logical_name)
        REFERENCES source_metadata(logical_source_name)
);

CREATE TABLE cycles (
    cycle_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    symbols_total INTEGER CHECK (symbols_total IS NULL OR symbols_total >= 0),
    symbols_processed INTEGER CHECK (symbols_processed IS NULL OR symbols_processed >= 0),
    signals_emitted INTEGER CHECK (signals_emitted IS NULL OR signals_emitted >= 0),
    signals_rejected INTEGER CHECK (signals_rejected IS NULL OR signals_rejected >= 0),
    errors_count INTEGER CHECK (errors_count IS NULL OR errors_count >= 0),
    git_commit_sha TEXT,
    deployment_id TEXT,
    config_hash TEXT,
    selected_engine TEXT,
    strategy_version TEXT,
    policy_version TEXT,
    experiment_id TEXT,
    source_logical_name TEXT NOT NULL,
    source_record_identity TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    raw_payload_json TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    UNIQUE (source_logical_name, source_record_identity),
    FOREIGN KEY (source_logical_name)
        REFERENCES source_metadata(logical_source_name)
);

CREATE TABLE signals (
    projection_key TEXT PRIMARY KEY,
    signal_id TEXT,
    observation_id TEXT,
    cycle_id TEXT,
    event_timestamp TEXT NOT NULL,
    symbol TEXT,
    direction TEXT,
    timeframe TEXT,
    setup TEXT,
    decision TEXT,
    status TEXT,
    accepted INTEGER CHECK (accepted IS NULL OR accepted IN (0, 1)),
    published INTEGER CHECK (published IS NULL OR published IN (0, 1)),
    rejected INTEGER CHECK (rejected IS NULL OR rejected IN (0, 1)),
    shadow INTEGER CHECK (shadow IS NULL OR shadow IN (0, 1)),
    rejection_reason TEXT,
    git_commit_sha TEXT,
    deployment_id TEXT,
    config_hash TEXT,
    selected_engine TEXT,
    strategy_version TEXT,
    policy_version TEXT,
    experiment_id TEXT,
    source_logical_name TEXT NOT NULL,
    source_record_identity TEXT NOT NULL,
    raw_payload_json TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    UNIQUE (source_logical_name, source_record_identity),
    FOREIGN KEY (source_logical_name)
        REFERENCES source_metadata(logical_source_name)
);

CREATE INDEX idx_system_snapshots_observed_at
    ON system_snapshots(observed_at DESC);
CREATE INDEX idx_system_snapshots_component
    ON system_snapshots(component, observed_at DESC);

CREATE INDEX idx_cycles_started_at
    ON cycles(started_at DESC);
CREATE INDEX idx_cycles_source
    ON cycles(source_logical_name, started_at DESC);
CREATE INDEX idx_cycles_status
    ON cycles(status, started_at DESC);
CREATE INDEX idx_cycles_strategy
    ON cycles(selected_engine, strategy_version, policy_version, started_at DESC);

CREATE INDEX idx_signals_timestamp
    ON signals(event_timestamp DESC);
CREATE INDEX idx_signals_source
    ON signals(source_logical_name, event_timestamp DESC);
CREATE INDEX idx_signals_cycle
    ON signals(cycle_id);
CREATE INDEX idx_signals_symbol
    ON signals(symbol, event_timestamp DESC);
CREATE INDEX idx_signals_decision
    ON signals(decision, status, event_timestamp DESC);
CREATE INDEX idx_signals_strategy
    ON signals(selected_engine, strategy_version, policy_version, event_timestamp DESC);
