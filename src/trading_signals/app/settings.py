from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _csv_env_fallback(name: str, fallback_name: str) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        raw = os.getenv(fallback_name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _qic_telegram_settings_explicit() -> bool:
    names = (
        "QIC_TELEGRAM_ENABLED",
        "QIC_TELEGRAM_BOT_TOKEN",
        "QIC_TELEGRAM_CHAT_ID",
        "AGENT_TELEGRAM_APPROVAL_ENABLED",
        "AGENT_TELEGRAM_BOT_TOKEN",
        "AGENT_TELEGRAM_CHAT_ID",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_DEV_CHAT_ID",
    )
    return any(name in os.environ for name in names)


def _publish_decisions_env(name: str, default: str) -> list[str]:
    values = [item.lower() for item in _csv_env(name, default)]
    if "both" in values:
        return ["long", "short"]
    return values


def _bool_env(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    market_data_provider: str = os.getenv("MARKET_DATA_PROVIDER", "binance")
    binance_base_url: str = os.getenv("BINANCE_BASE_URL", "https://api.binance.com/api/v3")
    binance_market_type: str = os.getenv("BINANCE_MARKET_TYPE", "spot")
    bybit_base_url: str = os.getenv("BYBIT_BASE_URL", "https://api.bybit.com")
    bybit_category: str = os.getenv("BYBIT_CATEGORY", "spot")
    scan_symbols: list[str] = field(
        default_factory=lambda: _csv_env(
            "SCAN_SYMBOLS",
            "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,DOGEUSDT,AVAXUSDT",
        )
    )
    entry_timeframe: str = os.getenv("ENTRY_TIMEFRAME", "1h")
    higher_timeframe: str = os.getenv("HIGHER_TIMEFRAME", "4h")
    setup_score_threshold: float = float(os.getenv("SETUP_SCORE_THRESHOLD", "45"))
    atr_min_threshold: float = float(os.getenv("ATR_MIN_THRESHOLD", "0.002"))
    max_distance_to_liquidity_atr: float = float(os.getenv("MAX_DISTANCE_TO_LIQUIDITY_ATR", "2.5"))
    min_body_ratio: float = float(os.getenv("MIN_BODY_RATIO", "0.35"))
    risk_per_trade: float = float(os.getenv("RISK_PER_TRADE", "0.01"))
    min_rr: float = float(os.getenv("MIN_RR", "2.0"))
    account_balance_reference: float = float(os.getenv("ACCOUNT_BALANCE_REFERENCE", "1000"))
    scan_interval_seconds: int = int(os.getenv("SCAN_INTERVAL_SECONDS", "900"))
    publish_signal_decisions: list[str] = field(default_factory=lambda: _publish_decisions_env("PUBLISH_SIGNAL_DECISIONS", "both"))
    publish_allowed_directions: list[str] = field(default_factory=lambda: _csv_env("PUBLISH_ALLOWED_DIRECTIONS", ""))
    publish_allowed_sessions: list[str] = field(default_factory=lambda: _csv_env("PUBLISH_ALLOWED_SESSIONS", ""))
    publish_allowed_hours_utc: list[str] = field(default_factory=lambda: _csv_env("PUBLISH_ALLOWED_HOURS_UTC", ""))
    publish_symbol_whitelist: list[str] = field(default_factory=lambda: _csv_env("PUBLISH_SYMBOL_WHITELIST", ""))
    publish_blocked_warnings: list[str] = field(default_factory=lambda: _csv_env("PUBLISH_BLOCKED_WARNINGS", ""))
    publish_blocked_reasons: list[str] = field(default_factory=lambda: _csv_env("PUBLISH_BLOCKED_REASONS", ""))
    publish_require_no_harmful_filters: bool = field(
        default_factory=lambda: _bool_env("PUBLISH_REQUIRE_NO_HARMFUL_FILTERS", "false")
    )
    use_modular_decision_engine: bool = field(default_factory=lambda: _bool_env("USE_MODULAR_DECISION_ENGINE", "false"))
    relaxed_strategy_gates_enabled: bool = field(default_factory=lambda: _bool_env("RELAXED_STRATEGY_GATES_ENABLED", "false"))
    meta_decision_filter_enabled: bool = field(default_factory=lambda: _bool_env("META_DECISION_FILTER_ENABLED", "false"))
    edge_activation_mode: bool = field(default_factory=lambda: _bool_env("EDGE_ACTIVATION_MODE", "true"))
    short_shadow_mode: bool = field(default_factory=lambda: _bool_env("SHORT_SHADOW_MODE", "true"))
    bullish_sweep_block_enabled: bool = field(default_factory=lambda: _bool_env("BULLISH_SWEEP_BLOCK_ENABLED", "false"))
    against_htf_breakout_block_enabled: bool = field(
        default_factory=lambda: _bool_env("AGAINST_HTF_BREAKOUT_BLOCK_ENABLED", "false")
    )
    strategy_v2_1_htf_alignment_filter_enabled: bool = field(
        default_factory=lambda: _bool_env("STRATEGY_V2_1_HTF_ALIGNMENT_FILTER_ENABLED", "false")
    )
    strategy_v2_1_htf_alignment_filter_mode: str = field(
        default_factory=lambda: os.getenv("STRATEGY_V2_1_HTF_ALIGNMENT_FILTER_MODE", "shadow")
    )
    adaptive_filter_enabled: bool = field(default_factory=lambda: _bool_env("ADAPTIVE_FILTER_ENABLED", "false"))
    adaptive_filter_mode: str = field(default_factory=lambda: os.getenv("ADAPTIVE_FILTER_MODE", "observe"))
    adaptive_filter_min_closed: int = field(default_factory=lambda: int(os.getenv("ADAPTIVE_FILTER_MIN_CLOSED", "30")))
    adaptive_filter_block_pf_threshold: float = field(
        default_factory=lambda: float(os.getenv("ADAPTIVE_FILTER_BLOCK_PF_THRESHOLD", "0.75"))
    )
    adaptive_filter_block_total_r_threshold: float = field(
        default_factory=lambda: float(os.getenv("ADAPTIVE_FILTER_BLOCK_TOTAL_R_THRESHOLD", "-5"))
    )
    adaptive_filter_unblock_pf_threshold: float = field(
        default_factory=lambda: float(os.getenv("ADAPTIVE_FILTER_UNBLOCK_PF_THRESHOLD", "1.20"))
    )
    adaptive_filter_unblock_total_r_threshold: float = field(
        default_factory=lambda: float(os.getenv("ADAPTIVE_FILTER_UNBLOCK_TOTAL_R_THRESHOLD", "5"))
    )
    adaptive_filter_allowed_contexts: list[str] = field(
        default_factory=lambda: _csv_env("ADAPTIVE_FILTER_ALLOWED_CONTEXTS", "bullish_sweep,against_htf_breakout")
    )
    adaptive_filter_require_human_approval: bool = field(
        default_factory=lambda: _bool_env("ADAPTIVE_FILTER_REQUIRE_HUMAN_APPROVAL", "true")
    )
    public_short_canary_enabled: bool = field(default_factory=lambda: _bool_env("PUBLIC_SHORT_CANARY_ENABLED", "false"))
    public_short_canary_session: str = field(default_factory=lambda: os.getenv("PUBLIC_SHORT_CANARY_SESSION", "LONDON"))
    public_short_canary_direction: str = field(default_factory=lambda: os.getenv("PUBLIC_SHORT_CANARY_DIRECTION", "SHORT"))
    public_short_canary_entry_context: str = field(default_factory=lambda: os.getenv("PUBLIC_SHORT_CANARY_ENTRY_CONTEXT", "PULLBACK"))
    public_short_canary_setup_type: str = field(default_factory=lambda: os.getenv("PUBLIC_SHORT_CANARY_SETUP_TYPE", "MAIN_SIGNAL"))
    public_short_canary_min_score: float = field(default_factory=lambda: float(os.getenv("PUBLIC_SHORT_CANARY_MIN_SCORE", "70")))
    relaxed_public_policy_runtime_shadow: bool = field(
        default_factory=lambda: _bool_env("RELAXED_PUBLIC_POLICY_RUNTIME_SHADOW", "true")
    )
    relaxed_public_policy_send_dev: bool = field(
        default_factory=lambda: _bool_env("RELAXED_PUBLIC_POLICY_SEND_DEV", "true")
    )
    kill_switch_enabled: bool = field(default_factory=lambda: _bool_env("KILL_SWITCH_ENABLED", "false"))
    max_daily_loss_r: float = field(default_factory=lambda: float(os.getenv("MAX_DAILY_LOSS_R", "2.0")))
    max_consecutive_losses: int = field(default_factory=lambda: int(os.getenv("MAX_CONSECUTIVE_LOSSES", "2")))
    max_weekly_drawdown_r: float = field(default_factory=lambda: float(os.getenv("MAX_WEEKLY_DRAWDOWN_R", "4.0")))
    kill_switch_cooldown_hours: int = field(default_factory=lambda: int(os.getenv("KILL_SWITCH_COOLDOWN_HOURS", "12")))
    protection_engine_mode: str = field(default_factory=lambda: os.getenv("PROTECTION_ENGINE_MODE", "shadow_only"))
    protection_symbol_loss_cooldown_hours: float = field(
        default_factory=lambda: float(os.getenv("PROTECTION_SYMBOL_LOSS_COOLDOWN_HOURS", "6"))
    )
    protection_symbol_rejection_threshold: int = field(
        default_factory=lambda: int(os.getenv("PROTECTION_SYMBOL_REJECTION_THRESHOLD", "3"))
    )
    protection_symbol_rejection_lookback_hours: float = field(
        default_factory=lambda: float(os.getenv("PROTECTION_SYMBOL_REJECTION_LOOKBACK_HOURS", "12"))
    )
    protection_symbol_rejection_cooldown_hours: float = field(
        default_factory=lambda: float(os.getenv("PROTECTION_SYMBOL_REJECTION_COOLDOWN_HOURS", "6"))
    )
    protection_max_drawdown_guard_r: float = field(
        default_factory=lambda: float(os.getenv("PROTECTION_MAX_DRAWDOWN_GUARD_R", "4.0"))
    )
    protection_max_drawdown_lookback_days: float = field(
        default_factory=lambda: float(os.getenv("PROTECTION_MAX_DRAWDOWN_LOOKBACK_DAYS", "7"))
    )
    protection_low_profit_min_trades: int = field(
        default_factory=lambda: int(os.getenv("PROTECTION_LOW_PROFIT_MIN_TRADES", "5"))
    )
    protection_low_profit_min_avg_r: float = field(
        default_factory=lambda: float(os.getenv("PROTECTION_LOW_PROFIT_MIN_AVG_R", "-0.2"))
    )
    protection_low_profit_lookback_days: float = field(
        default_factory=lambda: float(os.getenv("PROTECTION_LOW_PROFIT_LOOKBACK_DAYS", "14"))
    )
    protection_toxic_context_shadow_enabled: bool = field(
        default_factory=lambda: _bool_env("PROTECTION_TOXIC_CONTEXT_SHADOW_ENABLED", "true")
    )
    pair_universe_filter_mode: str = field(default_factory=lambda: os.getenv("PAIR_UNIVERSE_FILTER_MODE", "shadow_only"))
    pair_universe_min_volume: float = field(default_factory=lambda: float(os.getenv("PAIR_UNIVERSE_MIN_VOLUME", "0")))
    pair_universe_max_spread_pct: float = field(default_factory=lambda: float(os.getenv("PAIR_UNIVERSE_MAX_SPREAD_PCT", "5")))
    pair_universe_min_volatility_pct: float = field(
        default_factory=lambda: float(os.getenv("PAIR_UNIVERSE_MIN_VOLATILITY_PCT", "0.1"))
    )
    pair_universe_max_volatility_pct: float = field(
        default_factory=lambda: float(os.getenv("PAIR_UNIVERSE_MAX_VOLATILITY_PCT", "25"))
    )
    pair_universe_min_history_candles: int = field(
        default_factory=lambda: int(os.getenv("PAIR_UNIVERSE_MIN_HISTORY_CANDLES", "220"))
    )
    pair_universe_blacklist: list[str] = field(default_factory=lambda: _csv_env("PAIR_UNIVERSE_BLACKLIST", ""))
    pair_universe_whitelist: list[str] = field(default_factory=lambda: _csv_env("PAIR_UNIVERSE_WHITELIST", ""))
    pair_universe_rejection_threshold: int = field(
        default_factory=lambda: int(os.getenv("PAIR_UNIVERSE_REJECTION_THRESHOLD", "5"))
    )
    pair_universe_rejection_lookback_hours: float = field(
        default_factory=lambda: float(os.getenv("PAIR_UNIVERSE_REJECTION_LOOKBACK_HOURS", "24"))
    )
    pair_universe_min_recent_avg_r: float = field(
        default_factory=lambda: float(os.getenv("PAIR_UNIVERSE_MIN_RECENT_AVG_R", "-0.5"))
    )
    pair_universe_performance_min_trades: int = field(
        default_factory=lambda: int(os.getenv("PAIR_UNIVERSE_PERFORMANCE_MIN_TRADES", "3"))
    )
    pair_universe_performance_lookback_days: float = field(
        default_factory=lambda: float(os.getenv("PAIR_UNIVERSE_PERFORMANCE_LOOKBACK_DAYS", "14"))
    )
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_ids: list[str] = field(default_factory=lambda: _csv_env("TELEGRAM_CHAT_IDS", ""))
    telegram_public_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_PUBLIC_CHAT_ID", ""))
    telegram_dev_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_DEV_CHAT_ID", ""))
    telegram_dev_chat_ids: list[str] = field(default_factory=lambda: _csv_env("TELEGRAM_DEV_CHAT_ID", ""))
    telegram_allowed_private_chat_ids: list[str] = field(
        default_factory=lambda: _csv_env_fallback("TELEGRAM_ALLOWED_PRIVATE_CHAT_IDS", "TELEGRAM_DEV_CHAT_ID")
    )
    telegram_users_file: Path = field(
        default_factory=lambda: Path(os.getenv("TELEGRAM_USERS_FILE", "./telegram_users.json"))
    )
    telegram_state_file: Path = field(
        default_factory=lambda: Path(os.getenv("TELEGRAM_STATE_FILE", "./telegram_state.json"))
    )
    telegram_listener_sleep_seconds: int = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_LISTENER_SLEEP_SECONDS", "5"))
    )
    telegram_diagnostic_summary_enabled: bool = field(
        default_factory=lambda: _bool_env("TELEGRAM_DIAGNOSTIC_SUMMARY_ENABLED", "true")
    )
    telegram_diagnostic_summary_every_cycles: int = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_DIAGNOSTIC_SUMMARY_EVERY_CYCLES", "5"))
    )
    bot_health_telegram_enabled: bool = field(default_factory=lambda: _bool_env("BOT_HEALTH_TELEGRAM_ENABLED", "true"))
    bot_health_min_score: float = field(default_factory=lambda: float(os.getenv("BOT_HEALTH_MIN_SCORE", "70")))
    elite_profile_c_dev_note_enabled: bool = field(
        default_factory=lambda: _bool_env("ELITE_PROFILE_C_DEV_NOTE_ENABLED", "false")
    )
    elite_subprofile_dev_note_enabled: bool = field(
        default_factory=lambda: _bool_env("ELITE_SUBPROFILE_DEV_NOTE_ENABLED", "false")
    )
    signal_update_v1_dev_note_enabled: bool = field(
        default_factory=lambda: _bool_env("SIGNAL_UPDATE_V1_DEV_NOTE_ENABLED", "false")
    )
    active_signal_cleanup_enabled: bool = field(
        default_factory=lambda: _bool_env("ACTIVE_SIGNAL_CLEANUP_ENABLED", "false")
    )
    active_signal_cleanup_dry_run: bool = field(
        default_factory=lambda: _bool_env("ACTIVE_SIGNAL_CLEANUP_DRY_RUN", "true")
    )
    active_signal_cleanup_zombie_hours: float = field(
        default_factory=lambda: float(os.getenv("ACTIVE_SIGNAL_CLEANUP_ZOMBIE_HOURS", "48"))
    )
    active_signal_cleanup_dev_note_enabled: bool = field(
        default_factory=lambda: _bool_env("ACTIVE_SIGNAL_CLEANUP_DEV_NOTE_ENABLED", "false")
    )
    active_signal_expiration_enabled: bool = field(
        default_factory=lambda: _bool_env("ACTIVE_SIGNAL_EXPIRATION_ENABLED", "true")
    )
    active_signal_default_expiration_hours: float = field(
        default_factory=lambda: float(os.getenv("ACTIVE_SIGNAL_DEFAULT_EXPIRATION_HOURS", "48"))
    )
    active_signal_cleanup_scheduler_dry_run_enabled: bool = field(
        default_factory=lambda: _bool_env("ACTIVE_SIGNAL_CLEANUP_SCHEDULER_DRY_RUN_ENABLED", "true")
    )
    active_signal_cleanup_scheduler_dry_run_interval_cycles: int = field(
        default_factory=lambda: int(os.getenv("ACTIVE_SIGNAL_CLEANUP_SCHEDULER_DRY_RUN_INTERVAL_CYCLES", "1"))
    )
    active_signal_cleanup_scheduler_dry_run_dev_note_enabled: bool = field(
        default_factory=lambda: _bool_env("ACTIVE_SIGNAL_CLEANUP_SCHEDULER_DRY_RUN_DEV_NOTE_ENABLED", "false")
    )
    edge_knowledge_shadow_dev_note_enabled: bool = field(
        default_factory=lambda: _bool_env("EDGE_KNOWLEDGE_SHADOW_DEV_NOTE_ENABLED", "false")
    )
    edge_optimizer_active_enabled: bool = field(
        default_factory=lambda: _bool_env("EDGE_OPTIMIZER_ACTIVE_ENABLED", "false")
    )
    edge_optimizer_active_max_adjustment: float = field(
        default_factory=lambda: float(os.getenv("EDGE_OPTIMIZER_ACTIVE_MAX_ADJUSTMENT", "2.0"))
    )
    edge_optimizer_active_min_confidence: str = field(
        default_factory=lambda: os.getenv("EDGE_OPTIMIZER_ACTIVE_MIN_CONFIDENCE", "MEDIUM")
    )
    agent_committee_enabled: bool = field(
        default_factory=lambda: _bool_env("AGENT_COMMITTEE_ENABLED", "false")
    )
    agent_committee_min_confidence: str = field(
        default_factory=lambda: os.getenv("AGENT_COMMITTEE_MIN_CONFIDENCE", "MEDIUM")
    )
    agent_telegram_approval_enabled: bool = field(
        default_factory=lambda: _bool_env("AGENT_TELEGRAM_APPROVAL_ENABLED", "false")
    )
    agent_telegram_chat_id: str = field(default_factory=lambda: os.getenv("AGENT_TELEGRAM_CHAT_ID", ""))
    agent_telegram_bot_token: str = field(default_factory=lambda: os.getenv("AGENT_TELEGRAM_BOT_TOKEN", ""))
    qic_telegram_enabled: bool = field(default_factory=lambda: _bool_env("QIC_TELEGRAM_ENABLED", "false"))
    qic_telegram_chat_id: str = field(default_factory=lambda: os.getenv("QIC_TELEGRAM_CHAT_ID", ""))
    qic_telegram_bot_token: str = field(default_factory=lambda: os.getenv("QIC_TELEGRAM_BOT_TOKEN", ""))
    qic_telegram_settings_explicit: bool = field(
        default_factory=_qic_telegram_settings_explicit,
        repr=False,
    )
    qic_telegram_send_no_actionable: bool = field(
        default_factory=lambda: _bool_env("QIC_TELEGRAM_SEND_NO_ACTIONABLE", "true")
    )
    qic_telegram_min_priority: str = field(default_factory=lambda: os.getenv("QIC_TELEGRAM_MIN_PRIORITY", "MEDIUM"))
    qic_scheduler_enabled: bool = field(default_factory=lambda: _bool_env("QIC_SCHEDULER_ENABLED", "false"))
    qic_scheduler_interval_hours: float = field(
        default_factory=lambda: float(os.getenv("QIC_SCHEDULER_INTERVAL_HOURS", "6"))
    )
    qic_daily_summary_enabled: bool = field(default_factory=lambda: _bool_env("QIC_DAILY_SUMMARY_ENABLED", "true"))
    qic_daily_summary_hour: int = field(default_factory=lambda: int(os.getenv("QIC_DAILY_SUMMARY_HOUR", "9")))
    qic_daily_brief_enabled: bool = field(default_factory=lambda: _bool_env("QIC_DAILY_BRIEF_ENABLED", "true"))
    qic_weekly_research_review_enabled: bool = field(
        default_factory=lambda: _bool_env("QIC_WEEKLY_RESEARCH_REVIEW_ENABLED", "true")
    )
    qic_revalidation_min_new_trades: int = field(
        default_factory=lambda: int(os.getenv("QIC_REVALIDATION_MIN_NEW_TRADES", "50"))
    )
    qic_edge_confirmation_min_seen: int = field(
        default_factory=lambda: int(os.getenv("QIC_EDGE_CONFIRMATION_MIN_SEEN", "3"))
    )
    qic_edge_reproposal_cooldown_days: int = field(
        default_factory=lambda: int(os.getenv("QIC_EDGE_REPROPOSAL_COOLDOWN_DAYS", "14"))
    )
    qic_edge_degradation_pf_drop_pct: float = field(
        default_factory=lambda: float(os.getenv("QIC_EDGE_DEGRADATION_PF_DROP_PCT", "15"))
    )
    qic_code_engineer_enabled: bool = field(default_factory=lambda: _bool_env("QIC_CODE_ENGINEER_ENABLED", "false"))
    qic_code_engineer_allow_apply: bool = field(
        default_factory=lambda: _bool_env("QIC_CODE_ENGINEER_ALLOW_APPLY", "false")
    )
    qic_auto_apply_on_approval: bool = field(
        default_factory=lambda: _bool_env("QIC_AUTO_APPLY_ON_APPROVAL", "false")
    )
    qic_code_engineer_auto_commit: bool = field(
        default_factory=lambda: _bool_env("QIC_CODE_ENGINEER_AUTO_COMMIT", "false")
    )
    qic_code_engineer_max_autofix_attempts: int = field(
        default_factory=lambda: int(os.getenv("QIC_CODE_ENGINEER_MAX_AUTOFIX_ATTEMPTS", "1"))
    )
    qic_autonomous_enabled: bool = field(default_factory=lambda: _bool_env("QIC_AUTONOMOUS_ENABLED", "false"))
    qic_autonomous_dry_run: bool = field(default_factory=lambda: _bool_env("QIC_AUTONOMOUS_DRY_RUN", "true"))
    qic_timezone: str = field(default_factory=lambda: os.getenv("QIC_TIMEZONE", "Europe/Madrid"))
    qic_phase_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("QIC_PHASE_TIMEOUT_SECONDS", "300"))
    )
    qic_phase_max_retries: int = field(default_factory=lambda: int(os.getenv("QIC_PHASE_MAX_RETRIES", "1")))
    qic_enabled_agents: list[str] = field(
        default_factory=lambda: _csv_env(
            "QIC_ENABLED_AGENTS",
            "research_director,strategy_director,risk_director,simulation_director",
        )
    )
    qic_lock_stale_minutes: int = field(default_factory=lambda: int(os.getenv("QIC_LOCK_STALE_MINUTES", "120")))
    qic_event_interval_hours: float = field(default_factory=lambda: float(os.getenv("QIC_EVENT_INTERVAL_HOURS", "1")))
    qic_revalidation_interval_hours: float = field(
        default_factory=lambda: float(os.getenv("QIC_REVALIDATION_INTERVAL_HOURS", "24"))
    )
    qic_health_interval_minutes: int = field(
        default_factory=lambda: int(os.getenv("QIC_HEALTH_INTERVAL_MINUTES", "5"))
    )
    qic_weekly_research_review_weekday: int = field(
        default_factory=lambda: int(os.getenv("QIC_WEEKLY_RESEARCH_REVIEW_WEEKDAY", "0"))
    )
    qic_weekly_research_review_hour: int = field(
        default_factory=lambda: int(os.getenv("QIC_WEEKLY_RESEARCH_REVIEW_HOUR", "9"))
    )
    qic_weekly_research_review_minute: int = field(
        default_factory=lambda: int(os.getenv("QIC_WEEKLY_RESEARCH_REVIEW_MINUTE", "15"))
    )
    qic_notification_cooldown_seconds: int = field(
        default_factory=lambda: int(os.getenv("QIC_NOTIFICATION_COOLDOWN_SECONDS", "900"))
    )
    qic_notification_rate_limit_per_hour: int = field(
        default_factory=lambda: int(os.getenv("QIC_NOTIFICATION_RATE_LIMIT_PER_HOUR", "20"))
    )
    qic_auto_apply_low_risk: bool = field(
        default_factory=lambda: _bool_env("QIC_AUTO_APPLY_LOW_RISK", "false")
    )
    qic_auto_apply_medium_risk: bool = field(
        default_factory=lambda: _bool_env("QIC_AUTO_APPLY_MEDIUM_RISK", "false")
    )
    qic_live_trading_changes_allowed: bool = field(
        default_factory=lambda: _bool_env("QIC_LIVE_TRADING_CHANGES_ALLOWED", "false")
    )
    qic_auto_apply_max_files: int = field(default_factory=lambda: int(os.getenv("QIC_AUTO_APPLY_MAX_FILES", "8")))
    qic_auto_apply_max_changed_lines: int = field(
        default_factory=lambda: int(os.getenv("QIC_AUTO_APPLY_MAX_CHANGED_LINES", "400"))
    )
    qic_change_allowlist: list[str] = field(
        default_factory=lambda: _csv_env(
            "QIC_CHANGE_ALLOWLIST",
            "src/trading_signals/agents,src/trading_signals/application/use_cases,tests,scripts,reports/qic,Planning,deploy/frontend,src/trading_signals/interfaces/frontend",
        )
    )
    qic_change_denylist: list[str] = field(
        default_factory=lambda: _csv_env(
            "QIC_CHANGE_DENYLIST",
            ".env,.env.*,config/qic_telegram.json,credentials,wallets,keys,live_trading,risk_plan,position_sizing",
        )
    )
    qic_api_actions_enabled: bool = field(default_factory=lambda: _bool_env("QIC_API_ACTIONS_ENABLED", "false"))
    qic_report_retention_days: int = field(default_factory=lambda: int(os.getenv("QIC_REPORT_RETENTION_DAYS", "90")))
    qic_data_freshness_hours: int = field(default_factory=lambda: int(os.getenv("QIC_DATA_FRESHNESS_HOURS", "12")))
    qic_report_freshness_hours: int = field(default_factory=lambda: int(os.getenv("QIC_REPORT_FRESHNESS_HOURS", "12")))
    private_runtime_report_enabled: bool = field(
        default_factory=lambda: _bool_env("PRIVATE_RUNTIME_REPORT_ENABLED", "true")
    )
    private_runtime_report_every_cycles: int = field(
        default_factory=lambda: int(os.getenv("PRIVATE_RUNTIME_REPORT_EVERY_CYCLES", "5"))
    )
    private_runtime_report_state_file: Path = field(
        default_factory=lambda: Path(os.getenv("PRIVATE_RUNTIME_REPORT_STATE_FILE", "./data/runtime/private_runtime_report_state.json"))
    )
    scheduler_diagnostic_state_file: Path = field(
        default_factory=lambda: Path(os.getenv("SCHEDULER_DIAGNOSTIC_STATE_FILE", "./data/scheduler_diagnostic_window.json"))
    )
    scheduler_heartbeat_file: Path = field(
        default_factory=lambda: Path(os.getenv("SCHEDULER_HEARTBEAT_FILE", "./data/runtime/scheduler_heartbeat.json"))
    )
    scheduler_lock_file: Path = field(
        default_factory=lambda: Path(os.getenv("SCHEDULER_LOCK_FILE", "./data/runtime/scheduler.lock"))
    )
    deployment_id: str = field(default_factory=lambda: os.getenv("DEPLOYMENT_ID", "unknown"))
    trading_commission_r: float = field(default_factory=lambda: float(os.getenv("TRADING_COMMISSION_R", "0.02")))
    trading_spread_r: float = field(default_factory=lambda: float(os.getenv("TRADING_SPREAD_R", "0.01")))
    trading_slippage_r: float = field(default_factory=lambda: float(os.getenv("TRADING_SLIPPAGE_R", "0.01")))
    trading_funding_r: float = field(default_factory=lambda: float(os.getenv("TRADING_FUNDING_R", "0")))
    paper_trading_enabled: bool = field(default_factory=lambda: _bool_env("PAPER_TRADING_ENABLED", "true"))
    paper_trading_strong_candidate_min_score: float = float(os.getenv("PAPER_TRADING_STRONG_CANDIDATE_MIN_SCORE", "35"))
    paper_trading_timeout_candles: int = int(os.getenv("PAPER_TRADING_TIMEOUT_CANDLES", "24"))
    paper_trading_min_rr: float = float(os.getenv("PAPER_TRADING_MIN_RR", "1.5"))
    paper_trading_max_spread_atr: float = float(os.getenv("PAPER_TRADING_MAX_SPREAD_ATR", "1.8"))
    paper_trading_atr_min_threshold: float = float(os.getenv("PAPER_TRADING_ATR_MIN_THRESHOLD", os.getenv("ATR_MIN_THRESHOLD", "0.002")))
    paper_trading_summary_enabled: bool = field(default_factory=lambda: _bool_env("TELEGRAM_PAPER_DAILY_SUMMARY_ENABLED", "true"))
    paper_trading_summary_state_file: Path = field(
        default_factory=lambda: Path(os.getenv("PAPER_TRADING_SUMMARY_STATE_FILE", "./data/paper_trading/daily_summary_state.json"))
    )
    live_trade_tracking_enabled: bool = field(default_factory=lambda: _bool_env("LIVE_TRADE_TRACKING_ENABLED", "true"))
    live_breakeven_alert_enabled: bool = field(default_factory=lambda: _bool_env("LIVE_BREAKEVEN_ALERT_ENABLED", "true"))
    live_breakeven_trigger_r: float = float(os.getenv("LIVE_BREAKEVEN_TRIGGER_R", "1.0"))
    live_partial_tp_alert_enabled: bool = field(default_factory=lambda: _bool_env("LIVE_PARTIAL_TP_ALERT_ENABLED", "true"))
    live_partial_tp_trigger_r: float = float(os.getenv("LIVE_PARTIAL_TP_TRIGGER_R", "1.5"))
    live_partial_tp_percentage_suggestion: str = os.getenv("LIVE_PARTIAL_TP_PERCENTAGE_SUGGESTION", "30-50")
    live_trading_summary_enabled: bool = field(default_factory=lambda: _bool_env("TELEGRAM_LIVE_DAILY_SUMMARY_ENABLED", "true"))
    live_trading_summary_state_file: Path = field(
        default_factory=lambda: Path(os.getenv("LIVE_TRADING_SUMMARY_STATE_FILE", "./data/live_trading/daily_summary_state.json"))
    )
    data_storage_path: Path = field(default_factory=lambda: Path(os.getenv("DATA_STORAGE_PATH", "./data")))
    diagnostics_path: Path = field(default_factory=lambda: Path(os.getenv("DIAGNOSTICS_PATH", "./data/diagnostics")))


def load_settings() -> Settings:
    settings = Settings()
    settings.data_storage_path.mkdir(parents=True, exist_ok=True)
    settings.diagnostics_path.mkdir(parents=True, exist_ok=True)
    return settings
