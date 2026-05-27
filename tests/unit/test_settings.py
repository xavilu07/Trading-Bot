from __future__ import annotations

from trading_signals.app.settings import Settings


def test_telegram_diagnostic_summary_settings_are_configurable(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_DIAGNOSTIC_SUMMARY_ENABLED", "false")
    monkeypatch.setenv("TELEGRAM_DIAGNOSTIC_SUMMARY_EVERY_CYCLES", "3")
    monkeypatch.setenv("BOT_HEALTH_TELEGRAM_ENABLED", "false")
    monkeypatch.setenv("BOT_HEALTH_MIN_SCORE", "80")
    monkeypatch.setenv("TELEGRAM_PUBLIC_CHAT_ID", "public-chat")
    monkeypatch.setenv("TELEGRAM_DEV_CHAT_ID", "dev-chat")

    settings = Settings()

    assert settings.telegram_diagnostic_summary_enabled is False
    assert settings.telegram_diagnostic_summary_every_cycles == 3
    assert settings.bot_health_telegram_enabled is False
    assert settings.bot_health_min_score == 80
    assert settings.telegram_public_chat_id == "public-chat"
    assert settings.telegram_dev_chat_id == "dev-chat"
    assert settings.telegram_dev_chat_ids == ["dev-chat"]
    assert settings.telegram_allowed_private_chat_ids == ["dev-chat"]


def test_telegram_dev_chat_id_supports_multiple_ids(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_DEV_CHAT_ID", "7437028098,1979812925")

    settings = Settings()

    assert settings.telegram_dev_chat_id == "7437028098,1979812925"
    assert settings.telegram_dev_chat_ids == ["7437028098", "1979812925"]
    assert settings.telegram_allowed_private_chat_ids == ["7437028098", "1979812925"]


def test_telegram_allowed_private_chat_ids_overrides_dev_fallback(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_DEV_CHAT_ID", "7437028098")
    monkeypatch.setenv("TELEGRAM_ALLOWED_PRIVATE_CHAT_IDS", "1979812925,7437028098")

    settings = Settings()

    assert settings.telegram_allowed_private_chat_ids == ["1979812925", "7437028098"]


def test_publish_signal_decisions_both_enables_long_and_short(monkeypatch) -> None:
    monkeypatch.setenv("PUBLISH_SIGNAL_DECISIONS", "both")

    settings = Settings()

    assert settings.publish_signal_decisions == ["long", "short"]


def test_publish_filters_are_configurable(monkeypatch) -> None:
    monkeypatch.setenv("PUBLISH_ALLOWED_DIRECTIONS", "LONG")
    monkeypatch.setenv("PUBLISH_ALLOWED_SESSIONS", "LONDON")
    monkeypatch.setenv("PUBLISH_ALLOWED_HOURS_UTC", "11,15")
    monkeypatch.setenv("PUBLISH_SYMBOL_WHITELIST", "AVAXUSDT,BTCUSDT")
    monkeypatch.setenv("PUBLISH_BLOCKED_WARNINGS", "distance_to_liquidity_penalty,directional_confluence_failed")
    monkeypatch.setenv("PUBLISH_BLOCKED_REASONS", "quality_score_failed")
    monkeypatch.setenv("PUBLISH_REQUIRE_NO_HARMFUL_FILTERS", "true")

    settings = Settings()

    assert settings.publish_allowed_directions == ["LONG"]
    assert settings.publish_allowed_sessions == ["LONDON"]
    assert settings.publish_allowed_hours_utc == ["11", "15"]
    assert settings.publish_symbol_whitelist == ["AVAXUSDT", "BTCUSDT"]
    assert settings.publish_blocked_warnings == ["distance_to_liquidity_penalty", "directional_confluence_failed"]
    assert settings.publish_blocked_reasons == ["quality_score_failed"]
    assert settings.publish_require_no_harmful_filters is True


def test_modular_decision_engine_flag_defaults_to_false(monkeypatch) -> None:
    monkeypatch.delenv("USE_MODULAR_DECISION_ENGINE", raising=False)

    settings = Settings()

    assert settings.use_modular_decision_engine is False


def test_modular_decision_engine_flag_is_configurable(monkeypatch) -> None:
    monkeypatch.setenv("USE_MODULAR_DECISION_ENGINE", "true")

    settings = Settings()

    assert settings.use_modular_decision_engine is True


def test_meta_decision_filter_defaults_to_false_and_is_configurable(monkeypatch) -> None:
    monkeypatch.delenv("META_DECISION_FILTER_ENABLED", raising=False)
    assert Settings().meta_decision_filter_enabled is False

    monkeypatch.setenv("META_DECISION_FILTER_ENABLED", "true")
    assert Settings().meta_decision_filter_enabled is True


def test_edge_activation_mode_defaults_to_true_and_is_configurable(monkeypatch) -> None:
    monkeypatch.delenv("EDGE_ACTIVATION_MODE", raising=False)
    assert Settings().edge_activation_mode is True

    monkeypatch.setenv("EDGE_ACTIVATION_MODE", "false")
    assert Settings().edge_activation_mode is False


def test_short_shadow_mode_defaults_to_true_and_is_configurable(monkeypatch) -> None:
    monkeypatch.delenv("SHORT_SHADOW_MODE", raising=False)
    assert Settings().short_shadow_mode is True

    monkeypatch.setenv("SHORT_SHADOW_MODE", "false")
    assert Settings().short_shadow_mode is False


def test_kill_switch_settings_are_configurable(monkeypatch) -> None:
    monkeypatch.setenv("KILL_SWITCH_ENABLED", "true")
    monkeypatch.setenv("MAX_DAILY_LOSS_R", "3.5")
    monkeypatch.setenv("MAX_CONSECUTIVE_LOSSES", "4")
    monkeypatch.setenv("MAX_WEEKLY_DRAWDOWN_R", "7.5")
    monkeypatch.setenv("KILL_SWITCH_COOLDOWN_HOURS", "24")

    settings = Settings()

    assert settings.kill_switch_enabled is True
    assert settings.max_daily_loss_r == 3.5
    assert settings.max_consecutive_losses == 4
    assert settings.max_weekly_drawdown_r == 7.5
    assert settings.kill_switch_cooldown_hours == 24


def test_protection_engine_settings_are_configurable(monkeypatch) -> None:
    monkeypatch.setenv("PROTECTION_ENGINE_MODE", "enforce_paper")
    monkeypatch.setenv("PROTECTION_SYMBOL_LOSS_COOLDOWN_HOURS", "8")
    monkeypatch.setenv("PROTECTION_SYMBOL_REJECTION_THRESHOLD", "4")
    monkeypatch.setenv("PROTECTION_SYMBOL_REJECTION_LOOKBACK_HOURS", "18")
    monkeypatch.setenv("PROTECTION_SYMBOL_REJECTION_COOLDOWN_HOURS", "9")
    monkeypatch.setenv("PROTECTION_MAX_DRAWDOWN_GUARD_R", "6")
    monkeypatch.setenv("PROTECTION_MAX_DRAWDOWN_LOOKBACK_DAYS", "10")
    monkeypatch.setenv("PROTECTION_LOW_PROFIT_MIN_TRADES", "7")
    monkeypatch.setenv("PROTECTION_LOW_PROFIT_MIN_AVG_R", "-0.4")
    monkeypatch.setenv("PROTECTION_LOW_PROFIT_LOOKBACK_DAYS", "21")
    monkeypatch.setenv("PROTECTION_TOXIC_CONTEXT_SHADOW_ENABLED", "false")

    settings = Settings()

    assert settings.protection_engine_mode == "enforce_paper"
    assert settings.protection_symbol_loss_cooldown_hours == 8
    assert settings.protection_symbol_rejection_threshold == 4
    assert settings.protection_symbol_rejection_lookback_hours == 18
    assert settings.protection_symbol_rejection_cooldown_hours == 9
    assert settings.protection_max_drawdown_guard_r == 6
    assert settings.protection_max_drawdown_lookback_days == 10
    assert settings.protection_low_profit_min_trades == 7
    assert settings.protection_low_profit_min_avg_r == -0.4
    assert settings.protection_low_profit_lookback_days == 21
    assert settings.protection_toxic_context_shadow_enabled is False


def test_pair_universe_filter_settings_are_configurable(monkeypatch) -> None:
    monkeypatch.setenv("PAIR_UNIVERSE_FILTER_MODE", "enforce_paper")
    monkeypatch.setenv("PAIR_UNIVERSE_MIN_VOLUME", "1000")
    monkeypatch.setenv("PAIR_UNIVERSE_MAX_SPREAD_PCT", "2.5")
    monkeypatch.setenv("PAIR_UNIVERSE_MIN_VOLATILITY_PCT", "0.3")
    monkeypatch.setenv("PAIR_UNIVERSE_MAX_VOLATILITY_PCT", "15")
    monkeypatch.setenv("PAIR_UNIVERSE_MIN_HISTORY_CANDLES", "250")
    monkeypatch.setenv("PAIR_UNIVERSE_BLACKLIST", "DOGEUSDT,XRPUSDT")
    monkeypatch.setenv("PAIR_UNIVERSE_WHITELIST", "BTCUSDT,ETHUSDT")
    monkeypatch.setenv("PAIR_UNIVERSE_REJECTION_THRESHOLD", "8")
    monkeypatch.setenv("PAIR_UNIVERSE_REJECTION_LOOKBACK_HOURS", "48")
    monkeypatch.setenv("PAIR_UNIVERSE_MIN_RECENT_AVG_R", "-0.25")
    monkeypatch.setenv("PAIR_UNIVERSE_PERFORMANCE_MIN_TRADES", "5")
    monkeypatch.setenv("PAIR_UNIVERSE_PERFORMANCE_LOOKBACK_DAYS", "30")

    settings = Settings()

    assert settings.pair_universe_filter_mode == "enforce_paper"
    assert settings.pair_universe_min_volume == 1000
    assert settings.pair_universe_max_spread_pct == 2.5
    assert settings.pair_universe_min_volatility_pct == 0.3
    assert settings.pair_universe_max_volatility_pct == 15
    assert settings.pair_universe_min_history_candles == 250
    assert settings.pair_universe_blacklist == ["DOGEUSDT", "XRPUSDT"]
    assert settings.pair_universe_whitelist == ["BTCUSDT", "ETHUSDT"]
    assert settings.pair_universe_rejection_threshold == 8
    assert settings.pair_universe_rejection_lookback_hours == 48
    assert settings.pair_universe_min_recent_avg_r == -0.25
    assert settings.pair_universe_performance_min_trades == 5
    assert settings.pair_universe_performance_lookback_days == 30


def test_market_data_provider_defaults_to_binance(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_DATA_PROVIDER", raising=False)

    settings = Settings()

    assert settings.market_data_provider == "binance"
    assert settings.binance_base_url == "https://api.binance.com/api/v3"


def test_scheduler_heartbeat_file_is_configurable(monkeypatch) -> None:
    monkeypatch.setenv("SCHEDULER_HEARTBEAT_FILE", "./tmp/heartbeat.json")

    settings = Settings()

    assert str(settings.scheduler_heartbeat_file) == "tmp/heartbeat.json"
