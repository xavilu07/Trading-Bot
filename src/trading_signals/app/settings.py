from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


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
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_ids: list[str] = field(default_factory=lambda: _csv_env("TELEGRAM_CHAT_IDS", ""))
    telegram_public_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_PUBLIC_CHAT_ID", ""))
    telegram_dev_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_DEV_CHAT_ID", ""))
    telegram_users_file: Path = field(
        default_factory=lambda: Path(os.getenv("TELEGRAM_USERS_FILE", "./telegram_users.json"))
    )
    telegram_state_file: Path = field(
        default_factory=lambda: Path(os.getenv("TELEGRAM_STATE_FILE", "./telegram_state.json"))
    )
    telegram_listener_sleep_seconds: int = int(os.getenv("TELEGRAM_LISTENER_SLEEP_SECONDS", "5"))
    telegram_diagnostic_summary_enabled: bool = field(
        default_factory=lambda: _bool_env("TELEGRAM_DIAGNOSTIC_SUMMARY_ENABLED", "true")
    )
    telegram_diagnostic_summary_every_cycles: int = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_DIAGNOSTIC_SUMMARY_EVERY_CYCLES", "5"))
    )
    scheduler_diagnostic_state_file: Path = field(
        default_factory=lambda: Path(os.getenv("SCHEDULER_DIAGNOSTIC_STATE_FILE", "./data/scheduler_diagnostic_window.json"))
    )
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
