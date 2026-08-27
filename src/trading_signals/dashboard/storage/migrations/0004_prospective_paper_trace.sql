CREATE TABLE paper_trace_receipts (
    receipt_id TEXT PRIMARY KEY,
    receipt_hash TEXT NOT NULL CHECK(length(receipt_hash)=64),
    trace_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN (
        'SIGNAL_OBSERVED','SIGNAL_ACCEPTED','SIGNAL_REJECTED',
        'PAPER_ORDER_CREATED','PAPER_ORDER_CANCELLED','MARKET_CANDLE_OBSERVED',
        'ENTRY_TOUCHED','ENTRY_TOUCH_AMBIGUOUS','SIMULATED_FILL_CREATED',
        'PAPER_POSITION_OPENED','STOP_TOUCHED','TARGET_TOUCHED',
        'EXIT_AMBIGUOUS','PAPER_POSITION_CLOSED',
        'SIGNAL_EXPIRED_NOT_ACTIVATED','POSITION_HORIZON_REACHED',
        'POSITION_EXPIRED_CLOSED','POSITION_EXPIRED_UNRESOLVED',
        'MARKET_DATA_GAP','MARKET_DATA_CONFLICT','TRACE_ERROR'
    )),
    event_version TEXT NOT NULL,
    event_sequence INTEGER NOT NULL CHECK(event_sequence > 0),
    previous_receipt_id TEXT,
    occurred_at TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    order_id TEXT,
    fill_id TEXT,
    position_id TEXT,
    candle_open_time TEXT,
    timeframe TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('long','short')),
    price REAL,
    quantity REAL,
    evidence_id TEXT,
    evidence_fingerprint TEXT NOT NULL CHECK(length(evidence_fingerprint)=64),
    policy_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source='PROSPECTIVE_PAPER_TRACE'),
    reason_code TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
    created_at TEXT NOT NULL,
    projected_at TEXT NOT NULL,
    UNIQUE(trace_id, event_sequence),
    UNIQUE(trace_id, event_type, candle_open_time, evidence_fingerprint)
);

CREATE TABLE paper_trace_states (
    trace_id TEXT PRIMARY KEY,
    signal_id TEXT NOT NULL,
    signal_state TEXT NOT NULL CHECK(signal_state IN (
        'NONE','OBSERVED','ACCEPTED','REJECTED','EXPIRED_NOT_ACTIVATED'
    )),
    order_state TEXT NOT NULL CHECK(order_state IN (
        'NONE','PENDING','ACTIVATED','FILLED','CANCELLED','EXPIRED'
    )),
    position_state TEXT NOT NULL CHECK(position_state IN (
        'NONE','OPEN','CLOSED_WIN','CLOSED_LOSS','HORIZON_REACHED',
        'CLOSED_TIME_EXIT','EXPIRED_UNRESOLVED','AMBIGUOUS','DATA_BLOCKED'
    )),
    last_receipt_id TEXT NOT NULL,
    last_sequence INTEGER NOT NULL CHECK(last_sequence > 0),
    candles_before_entry INTEGER NOT NULL CHECK(candles_before_entry >= 0),
    candles_after_entry INTEGER NOT NULL CHECK(candles_after_entry >= 0),
    last_candle_open_time TEXT,
    trace_blocked_reason TEXT,
    policy_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source='PROSPECTIVE_PAPER_TRACE'),
    projected_at TEXT NOT NULL
);

CREATE INDEX idx_paper_trace_receipts_trace
    ON paper_trace_receipts(trace_id, event_sequence);
CREATE INDEX idx_paper_trace_receipts_event
    ON paper_trace_receipts(event_type, occurred_at);
CREATE INDEX idx_paper_trace_receipts_signal
    ON paper_trace_receipts(signal_id, occurred_at);
CREATE INDEX idx_paper_trace_receipts_symbol
    ON paper_trace_receipts(symbol, timeframe, occurred_at);
CREATE INDEX idx_paper_trace_receipts_policy
    ON paper_trace_receipts(policy_id, policy_version, model_version);
CREATE INDEX idx_paper_trace_states_status
    ON paper_trace_states(signal_state, order_state, position_state);
