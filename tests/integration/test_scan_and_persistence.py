from datetime import UTC, datetime
from pathlib import Path

from trading_signals.app.settings import Settings
from trading_signals.application.use_cases.run_market_scan import run_market_scan
from trading_signals.infrastructure.metrics.noop_metrics import NoopMetrics
from trading_signals.infrastructure.notifications.telegram_notifier import TelegramNotifier
from trading_signals.infrastructure.persistence.file_store import FileStore
from trading_signals.infrastructure.persistence.repositories import FileScanRunRepository, FileSignalRepository
from trading_signals.application.use_cases.paper_trading import PaperTradingStore
from trading_signals.application.use_cases.live_trading import LiveTradingStore
from trading_signals.memory.pattern_store import PatternMemoryStore
from tests.fixtures.market_data import FakeMarketDataClient, generate_trend_dataset


class ValidatingFakeMarketDataClient(FakeMarketDataClient):
    provider_name = "fake"

    def __init__(self, datasets, unsupported: set[str] | None = None) -> None:
        super().__init__(datasets)
        self.unsupported = unsupported or set()

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.strip().upper()

    def validate_symbol(self, symbol: str) -> bool:
        return self.normalize_symbol(symbol) not in self.unsupported

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300):
        return self.fetch_ohlcv(symbol, timeframe, limit=limit)


def test_scan_persists_entities_and_signals(tmp_path: Path) -> None:
    settings = Settings(data_storage_path=tmp_path, telegram_chat_ids=["dry"])
    dataset = generate_trend_dataset(direction="up")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): dataset,
        ("BTCUSDT", "4h"): dataset,
    })
    store = FileStore(tmp_path)
    result = run_market_scan(
        settings=settings,
        market_data=market_data,
        scan_repo=FileScanRunRepository(store),
        signal_repo=FileSignalRepository(store),
        notifier=TelegramNotifier("", ["dry"], tmp_path / "telegram_users.json", tmp_path / "telegram_state.json"),
        diagnostics_store=FileStore(tmp_path / "diagnostics"),
        metrics=NoopMetrics(),
        symbols=["BTCUSDT"],
        dry_run=True,
    )
    assert result["scan_run"]["symbols_processed"] == 1
    assert (tmp_path / "trade_signals").exists()
    files = list((tmp_path / "trade_signals").glob("**/*.json"))
    assert files


def test_scan_run_config_uses_effective_symbols(tmp_path: Path) -> None:
    settings = Settings(data_storage_path=tmp_path, telegram_chat_ids=["dry"])
    dataset = generate_trend_dataset(direction="down")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): dataset,
        ("BTCUSDT", "4h"): dataset,
        ("ETHUSDT", "1h"): dataset,
        ("ETHUSDT", "4h"): dataset,
    })
    store = FileStore(tmp_path)

    result = run_market_scan(
        settings=settings,
        market_data=market_data,
        scan_repo=FileScanRunRepository(store),
        signal_repo=FileSignalRepository(store),
        notifier=TelegramNotifier("", ["dry"], tmp_path / "telegram_users.json", tmp_path / "telegram_state.json"),
        diagnostics_store=FileStore(tmp_path / "diagnostics"),
        metrics=NoopMetrics(),
        symbols=[" btcusdt ", "ethusdt"],
        dry_run=True,
    )

    assert result["scan_run"]["symbols_total"] == 2
    assert result["scan_run"]["symbols_processed"] == 2
    assert result["scan_run"]["config"]["symbols"] == ["BTCUSDT", "ETHUSDT"]


def test_scan_skips_unsupported_and_insufficient_history_symbols(tmp_path: Path) -> None:
    settings = Settings(data_storage_path=tmp_path, telegram_chat_ids=["dry"])
    full_dataset = generate_trend_dataset(direction="down")
    short_dataset = generate_trend_dataset(rows=100, direction="down")
    market_data = ValidatingFakeMarketDataClient(
        {
            ("BTCUSDT", "1h"): full_dataset,
            ("BTCUSDT", "4h"): full_dataset,
            ("SHORTUSDT", "1h"): short_dataset,
            ("SHORTUSDT", "4h"): short_dataset,
        },
        unsupported={"MISSINGUSDT"},
    )
    store = FileStore(tmp_path)

    result = run_market_scan(
        settings=settings,
        market_data=market_data,
        scan_repo=FileScanRunRepository(store),
        signal_repo=FileSignalRepository(store),
        notifier=TelegramNotifier("", ["dry"], tmp_path / "telegram_users.json", tmp_path / "telegram_state.json"),
        diagnostics_store=FileStore(tmp_path / "diagnostics"),
        metrics=NoopMetrics(),
        symbols=["BTCUSDT", "MISSINGUSDT", "SHORTUSDT"],
        dry_run=True,
    )

    validation = result["universe_validation"]
    assert result["scan_run"]["symbols_total"] == 3
    assert result["scan_run"]["symbols_processed"] == 1
    assert result["scan_run"]["errors_count"] == 0
    assert validation["valid_symbols"] == ["BTCUSDT"]
    assert validation["skipped_reasons"] == {"unsupported_symbol": 1, "insufficient_history": 1}
    assert {item["symbol"] for item in validation["skipped_symbols"]} == {"MISSINGUSDT", "SHORTUSDT"}


def test_scan_creates_paper_trade_for_real_signal(tmp_path: Path) -> None:
    settings = Settings(data_storage_path=tmp_path, telegram_chat_ids=["dry"], publish_signal_decisions=["long"])
    dataset = generate_trend_dataset(direction="up")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): dataset,
        ("BTCUSDT", "4h"): dataset,
    })
    store = FileStore(tmp_path)
    paper_store = PaperTradingStore(tmp_path)

    result = run_market_scan(
        settings=settings,
        market_data=market_data,
        scan_repo=FileScanRunRepository(store),
        signal_repo=FileSignalRepository(store),
        notifier=TelegramNotifier("", ["dry"], tmp_path / "telegram_users.json", tmp_path / "telegram_state.json"),
        diagnostics_store=FileStore(tmp_path / "diagnostics"),
        metrics=NoopMetrics(),
        paper_trading_store=paper_store,
        symbols=["BTCUSDT"],
        dry_run=True,
    )

    assert result["results"][0]["signal"]["decision"] == "long"
    assert result["results"][0]["paper_trade_created"] is True
    trades = paper_store.list_trades()
    assert len(trades) == 1
    assert trades[0]["symbol"] == "BTCUSDT"
    assert trades[0]["status"] == "open"
    signal = result["results"][0]["signal"]
    for field in (
        "git_commit_sha",
        "deployment_id",
        "config_hash",
        "selected_engine",
        "strategy_version",
        "policy_version",
        "experiment_id",
    ):
        assert trades[0][field] == signal[field]
    assert signal["selected_engine"] != "unknown"
    assert signal["strategy_version"]
    assert signal["policy_version"] != "unknown"


def test_scan_creates_live_trade_for_real_published_signal(tmp_path: Path) -> None:
    settings = Settings(
        data_storage_path=tmp_path,
        telegram_chat_ids=["dry"],
        publish_signal_decisions=["long"],
        live_trade_tracking_enabled=True,
    )
    dataset = generate_trend_dataset(direction="up")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): dataset,
        ("BTCUSDT", "4h"): dataset,
    })
    store = FileStore(tmp_path)
    live_store = LiveTradingStore(tmp_path)

    result = run_market_scan(
        settings=settings,
        market_data=market_data,
        scan_repo=FileScanRunRepository(store),
        signal_repo=FileSignalRepository(store),
        notifier=TelegramNotifier("", ["dry"], tmp_path / "telegram_users.json", tmp_path / "telegram_state.json"),
        diagnostics_store=FileStore(tmp_path / "diagnostics"),
        metrics=NoopMetrics(),
        live_trading_store=live_store,
        symbols=["BTCUSDT"],
        dry_run=True,
    )

    assert result["results"][0]["signal"]["status"] == "published"
    trades = live_store.list_trades()
    assert len(trades) == 1
    assert trades[0]["symbol"] == "BTCUSDT"
    assert trades[0]["status"] == "open"
    assert trades[0]["signal_type"] == "NEW"


def test_duplicate_signal_is_not_published_twice(tmp_path: Path) -> None:
    settings = Settings(data_storage_path=tmp_path, telegram_chat_ids=["dry"], publish_signal_decisions=["long"])
    dataset = generate_trend_dataset(direction="up")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): dataset,
        ("BTCUSDT", "4h"): dataset,
    })
    store = FileStore(tmp_path)
    scan_repo = FileScanRunRepository(store)
    signal_repo = FileSignalRepository(store)
    notifier = TelegramNotifier("", ["dry"], tmp_path / "telegram_users.json", tmp_path / "telegram_state.json")
    metrics = NoopMetrics()

    first = run_market_scan(
        settings=settings,
        market_data=market_data,
        scan_repo=scan_repo,
        signal_repo=signal_repo,
        notifier=notifier,
        diagnostics_store=FileStore(tmp_path / "diagnostics"),
        metrics=metrics,
        symbols=["BTCUSDT"],
        dry_run=True,
    )
    second = run_market_scan(
        settings=settings,
        market_data=market_data,
        scan_repo=scan_repo,
        signal_repo=signal_repo,
        notifier=notifier,
        diagnostics_store=FileStore(tmp_path / "diagnostics"),
        metrics=metrics,
        symbols=["BTCUSDT"],
        dry_run=True,
    )

    first_signal = first["results"][0]["signal"]
    second_eval = second["results"][0]["evaluation"]
    assert first_signal["published_at"] is not None
    assert "duplicate_signal_suppressed" in second_eval["rejection_reasons"]


def test_no_trade_diagnostics_csv_is_written(tmp_path: Path) -> None:
    settings = Settings(data_storage_path=tmp_path, telegram_chat_ids=["dry"], diagnostics_path=tmp_path / "diagnostics")
    downtrend = generate_trend_dataset(direction="down")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): downtrend,
        ("BTCUSDT", "4h"): downtrend,
    })
    store = FileStore(tmp_path)
    diagnostics_store = FileStore(tmp_path / "diagnostics")

    result = run_market_scan(
        settings=settings,
        market_data=market_data,
        scan_repo=FileScanRunRepository(store),
        signal_repo=FileSignalRepository(store),
        notifier=TelegramNotifier("", ["dry"], tmp_path / "telegram_users.json", tmp_path / "telegram_state.json"),
        diagnostics_store=diagnostics_store,
        metrics=NoopMetrics(),
        symbols=["BTCUSDT"],
        dry_run=True,
    )

    assert result["results"][0]["signal"]["decision"] == "no_trade"
    csv_files = list((tmp_path / "diagnostics" / "no_trade_diagnostics").glob("*.csv"))
    assert csv_files
    content = csv_files[0].read_text(encoding="utf-8")
    assert "timestamp,scan_run_id,symbol,decision,setup_score" in content
    assert "BTCUSDT" in content
    rejection_reason = result["results"][0]["evaluation"]["rejection_reasons"][0]
    assert rejection_reason in content


def test_scan_adds_multi_agent_shadow_decision_without_changing_real_decision(tmp_path: Path) -> None:
    settings = Settings(data_storage_path=tmp_path, telegram_chat_ids=["dry"], publish_signal_decisions=["long"])
    dataset = generate_trend_dataset(direction="up")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): dataset,
        ("BTCUSDT", "4h"): dataset,
    })
    store = FileStore(tmp_path)

    result = run_market_scan(
        settings=settings,
        market_data=market_data,
        scan_repo=FileScanRunRepository(store),
        signal_repo=FileSignalRepository(store),
        notifier=TelegramNotifier("", ["dry"], tmp_path / "telegram_users.json", tmp_path / "telegram_state.json"),
        diagnostics_store=FileStore(tmp_path / "diagnostics"),
        metrics=NoopMetrics(),
        pattern_memory_store=PatternMemoryStore(tmp_path),
        symbols=["BTCUSDT"],
        dry_run=True,
    )

    item = result["results"][0]
    shadow_decision = item["multi_agent_shadow_decision"]
    assert item["signal"]["decision"] == "long"
    assert shadow_decision["mode"] == "SHADOW"
    assert shadow_decision["consensus_action"] in {"ALLOW", "CAUTION", "WOULD_BLOCK", "PRIORITIZE"}
    assert len(shadow_decision["votes"]) == 4
    assert item["pattern_memory"]["multi_agent_shadow_decision"] == shadow_decision


def test_meta_decision_filter_blocks_public_but_keeps_dev_and_live_tracking(tmp_path: Path, monkeypatch, caplog) -> None:
    def fake_performance_intelligence(*, pattern_record, pattern_history):
        return {
            "similar_count": 20,
            "meta_decision": {
                "meta_decision": "REJECT",
                "capital_preservation_mode": False,
                "meta_confidence": "HIGH",
                "meta_decision_score": 20,
            },
            "trade_quality": {
                "trade_quality_grade": "B",
                "quality_confidence": "HIGH",
                "trade_quality_score": 70,
            },
            "historical_edge": {
                "historical_edge_score": 30,
                "historical_confidence": "HIGH",
                "matched_patterns_count": 20,
                "matched_profit_factor": 0.8,
                "matched_avg_r": -0.2,
            },
        }

    monkeypatch.setattr(
        "trading_signals.application.use_cases.run_market_scan.build_performance_intelligence",
        fake_performance_intelligence,
    )
    settings = Settings(
        data_storage_path=tmp_path,
        telegram_chat_ids=["dry"],
        publish_signal_decisions=["long"],
        live_trade_tracking_enabled=True,
        meta_decision_filter_enabled=True,
    )
    dataset = generate_trend_dataset(direction="up")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): dataset,
        ("BTCUSDT", "4h"): dataset,
    })
    store = FileStore(tmp_path)
    live_store = LiveTradingStore(tmp_path)

    with caplog.at_level("INFO", logger="trading_signals"):
        result = run_market_scan(
            settings=settings,
            market_data=market_data,
            scan_repo=FileScanRunRepository(store),
            signal_repo=FileSignalRepository(store),
            notifier=TelegramNotifier("", ["dry"], tmp_path / "telegram_users.json", tmp_path / "telegram_state.json"),
            diagnostics_store=FileStore(tmp_path / "diagnostics"),
            metrics=NoopMetrics(),
            live_trading_store=live_store,
            pattern_memory_store=PatternMemoryStore(tmp_path),
            symbols=["BTCUSDT"],
            dry_run=True,
        )

    item = result["results"][0]
    assert item["signal"]["decision"] == "long"
    assert {delivery["channel"] for delivery in item["deliveries"]} == {"telegram_dev"}
    trades = live_store.list_trades()
    assert len(trades) == 1
    assert str(trades[0]["public_published"]).lower() == "false"
    assert "meta_decision_filter_blocked" in caplog.text
    assert "meta_decision_reject" in caplog.text


def test_kill_switch_blocks_public_but_keeps_dev_and_live_tracking(tmp_path: Path, caplog) -> None:
    closed_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat()
    paper_file = tmp_path / "paper_trading" / "trades.csv"
    paper_file.parent.mkdir(parents=True)
    paper_file.write_text(
        "status,result_r,closed_at\n"
        f"sl_hit,-2.5,{closed_at}\n",
        encoding="utf-8",
    )
    settings = Settings(
        data_storage_path=tmp_path,
        telegram_chat_ids=["dry"],
        publish_signal_decisions=["long"],
        live_trade_tracking_enabled=True,
        kill_switch_enabled=True,
        max_daily_loss_r=2.0,
        max_consecutive_losses=10,
        max_weekly_drawdown_r=10.0,
        kill_switch_cooldown_hours=0,
    )
    dataset = generate_trend_dataset(direction="up")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): dataset,
        ("BTCUSDT", "4h"): dataset,
    })
    store = FileStore(tmp_path)
    live_store = LiveTradingStore(tmp_path)

    with caplog.at_level("INFO", logger="trading_signals"):
        result = run_market_scan(
            settings=settings,
            market_data=market_data,
            scan_repo=FileScanRunRepository(store),
            signal_repo=FileSignalRepository(store),
            notifier=TelegramNotifier("", ["dry"], tmp_path / "telegram_users.json", tmp_path / "telegram_state.json"),
            diagnostics_store=FileStore(tmp_path / "diagnostics"),
            metrics=NoopMetrics(),
            live_trading_store=live_store,
            symbols=["BTCUSDT"],
            dry_run=True,
        )

    item = result["results"][0]
    assert item["signal"]["decision"] == "long"
    assert {delivery["channel"] for delivery in item["deliveries"]} == {"telegram_dev"}
    assert item["kill_switch"]["kill_switch_active"] is True
    trades = live_store.list_trades()
    assert len(trades) == 1
    assert str(trades[0]["public_published"]).lower() == "false"
    assert "kill_switch_blocked_public_signal" in caplog.text
    assert "daily_loss_limit" in caplog.text
