from __future__ import annotations

from trading_signals.app.settings import Settings


def test_telegram_diagnostic_summary_settings_are_configurable(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_DIAGNOSTIC_SUMMARY_ENABLED", "false")
    monkeypatch.setenv("TELEGRAM_DIAGNOSTIC_SUMMARY_EVERY_CYCLES", "3")
    monkeypatch.setenv("TELEGRAM_PUBLIC_CHAT_ID", "public-chat")
    monkeypatch.setenv("TELEGRAM_DEV_CHAT_ID", "dev-chat")

    settings = Settings()

    assert settings.telegram_diagnostic_summary_enabled is False
    assert settings.telegram_diagnostic_summary_every_cycles == 3
    assert settings.telegram_public_chat_id == "public-chat"
    assert settings.telegram_dev_chat_id == "dev-chat"


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


def test_market_data_provider_defaults_to_binance(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_DATA_PROVIDER", raising=False)

    settings = Settings()

    assert settings.market_data_provider == "binance"
    assert settings.binance_base_url == "https://api.binance.com/api/v3"
