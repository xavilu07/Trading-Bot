from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.application.use_cases.paper_stats import (
    build_paper_performance_summary,
    format_paper_performance_summary,
    format_paper_performance_summary_for_telegram,
    send_paper_performance_summary,
)


def write_trades(path: Path, rows: list[dict[str, object]]) -> None:
    trades_dir = path / "paper_trading"
    trades_dir.mkdir(parents=True)
    fields = sorted({key for row in rows for key in row})
    with (trades_dir / "trades.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_paper_stats_handles_missing_csv(tmp_path: Path) -> None:
    summary = build_paper_performance_summary(tmp_path)

    assert summary["trades_total"] == 0
    assert summary["closed_trades"] == 0
    assert summary["winrate"] == 0.0
    assert "Sin operaciones cerradas" in format_paper_performance_summary(summary)


def test_paper_stats_calculates_core_metrics_and_groups(tmp_path: Path) -> None:
    write_trades(
        tmp_path,
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "setup_type": "SECONDARY_SIGNAL",
                "paper_level": "HIGH",
                "status": "tp2_hit",
                "result_r": "2.0",
                "closed_at": "2026-01-03T00:00:00+00:00",
                "session": "LONDON",
                "opened_hour_utc": "10",
                "entry_or_rejection_reason": "paper_tradeable",
                "conditions_failed": '["distance_to_liquidity_penalty"]',
                "avoidance_warnings": '["low_volume"]',
            },
            {
                "symbol": "ETHUSDT",
                "direction": "short",
                "setup_type": "MAIN_SIGNAL",
                "paper_level": "MEDIUM",
                "status": "sl_hit",
                "result_r": "-1.0",
                "closed_at": "2026-01-04T00:00:00+00:00",
                "session": "NEW_YORK",
                "opened_hour_utc": "15",
                "entry_or_rejection_reason": "market_structure_range_penalty|quality_score_failed",
                "conditions_failed": '["quality_score_failed"]',
                "avoidance_warnings": '["dirty_sideways_market"]',
            },
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "status": "open",
                "result_r": "0.5",
                "session": "LONDON",
                "opened_hour_utc": "10",
            },
        ],
    )

    summary = build_paper_performance_summary(tmp_path)

    assert summary["trades_total"] == 3
    assert summary["closed_trades"] == 2
    assert summary["open_trades"] == 1
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["winrate"] == 50.0
    assert summary["total_r"] == 1.0
    assert summary["avg_r"] == 0.5
    assert summary["profit_factor"] == 2.0
    assert summary["by_direction"]["long"]["total_r"] == 2.0
    assert summary["by_direction"]["short"]["total_r"] == -1.0
    assert summary["by_setup_type"]["SECONDARY_SIGNAL"]["total_r"] == 2.0
    assert summary["by_paper_level"]["HIGH"]["total_r"] == 2.0
    assert summary["by_session"]["LONDON"]["total_r"] == 2.0
    assert summary["by_opened_hour_utc"]["10"]["total_r"] == 2.0
    assert summary["best_symbols"][0]["label"] == "BTCUSDT"
    assert summary["worst_symbols"][0]["label"] == "ETHUSDT"
    assert summary["top_failed_conditions"][0] == {"label": "distance_to_liquidity_penalty", "count": 1}
    assert summary["top_avoidance_warnings"][0] == {"label": "low_volume", "count": 1}
    assert len(summary["latest_10_closed"]) == 2


def test_paper_stats_tolerates_missing_columns(tmp_path: Path) -> None:
    write_trades(
        tmp_path,
        [
            {"symbol": "BTCUSDT", "status": "tp_hit", "result_r": "1.5"},
            {"symbol": "ETHUSDT", "status": "expired", "result_r": "0"},
        ],
    )

    summary = build_paper_performance_summary(tmp_path)
    output = format_paper_performance_summary(summary)

    assert summary["closed_trades"] == 2
    assert summary["wins"] == 1
    assert summary["expired"] == 1
    assert "Resumen rendimiento paper trading" in output


def test_paper_stats_recommendation_classifies_keep_pause_and_shadow(tmp_path: Path) -> None:
    rows = []
    for idx in range(4):
        rows.append({
            "symbol": "BTCUSDT",
            "direction": "long",
            "setup_type": "SECONDARY_SIGNAL",
            "paper_level": "HIGH",
            "session": "LONDON",
            "opened_hour_utc": "10",
            "status": "tp2_hit",
            "result_r": "1.5",
            "closed_at": f"2026-01-{idx + 1:02d}",
        })
    for idx in range(4):
        rows.append({
            "symbol": "ETHUSDT",
            "direction": "short",
            "setup_type": "MAIN_SIGNAL",
            "paper_level": "LOW",
            "session": "NEW_YORK",
            "opened_hour_utc": "22",
            "status": "sl_hit",
            "result_r": "-1",
            "closed_at": f"2026-01-{idx + 5:02d}",
        })
    for idx in range(2):
        rows.append({
            "symbol": "SOLUSDT",
            "direction": "long",
            "setup_type": "MAIN_SIGNAL",
            "paper_level": "MEDIUM",
            "session": "OVERLAP",
            "opened_hour_utc": "15",
            "status": "expired",
            "result_r": "0",
            "closed_at": f"2026-01-{idx + 9:02d}",
        })
    write_trades(tmp_path, rows)

    summary = build_paper_performance_summary(tmp_path)
    output = format_paper_performance_summary(summary)

    assert any("direction:long" in item for item in summary["recommendation"]["keep"])
    assert any("direction:short" in item for item in summary["recommendation"]["pause"])
    assert "Recomendación automática" in output


def test_filter_impact_ranks_useful_neutral_and_harmful_filters(tmp_path: Path) -> None:
    rows = []
    for idx in range(3):
        rows.append({
            "symbol": "BTCUSDT",
            "direction": "long",
            "status": "tp2_hit",
            "result_r": "1.0",
            "closed_at": f"2026-01-{idx + 1:02d}",
            "entry_or_rejection_reason": "useful_filter",
            "conditions_failed": '["useful_filter"]',
            "avoidance_warnings": "[]",
        })
    for idx in range(3):
        rows.append({
            "symbol": "ETHUSDT",
            "direction": "short",
            "status": "sl_hit",
            "result_r": "-1.0",
            "closed_at": f"2026-01-{idx + 4:02d}",
            "entry_or_rejection_reason": "harmful_filter",
            "conditions_failed": '["harmful_filter"]',
            "avoidance_warnings": '["dirty_sideways_market"]',
        })
    for idx in range(4):
        rows.append({
            "symbol": "SOLUSDT",
            "direction": "long",
            "status": "expired",
            "result_r": "0.0",
            "closed_at": f"2026-01-{idx + 7:02d}",
            "entry_or_rejection_reason": "neutral_filter",
            "conditions_failed": '["neutral_filter"]',
            "avoidance_warnings": "[]",
            "entry_reasons": '["penalties=neutral_filter:10"]',
        })
    write_trades(tmp_path, rows)

    summary = build_paper_performance_summary(tmp_path)
    impact = summary["filter_impact"]
    output = format_paper_performance_summary(summary)

    assert impact["useful"][0]["filter"] == "useful_filter"
    assert any(row["filter"] == "harmful_filter" for row in impact["harmful"])
    assert any(row["filter"] == "neutral_filter" for row in impact["neutral"])
    assert "Impacto de filtros/penalizaciones" in output
    assert "Filtros útiles" in output


def test_format_paper_stats_for_telegram_contains_key_sections(tmp_path: Path) -> None:
    write_trades(
        tmp_path,
        [
            {"symbol": "BTCUSDT", "direction": "long", "status": "tp2_hit", "result_r": "2", "closed_at": "2026-01-01"},
            {"symbol": "ETHUSDT", "direction": "short", "status": "sl_hit", "result_r": "-1", "closed_at": "2026-01-02"},
        ],
    )
    summary = build_paper_performance_summary(tmp_path)

    message = format_paper_performance_summary_for_telegram(summary)

    assert "📊 Paper Trading Summary" in message
    assert "Trades cerrados: 2" in message
    assert "Winrate: 50.0%" in message
    assert "Total R: 1.0R" in message
    assert "LONG vs SHORT" in message
    assert "Mejores símbolos" in message
    assert "Peores símbolos" in message
    assert "Setup / Nivel" in message
    assert "Recomendación" in message


def test_send_paper_stats_uses_notifier_publish(tmp_path: Path) -> None:
    write_trades(
        tmp_path,
        [{"symbol": "BTCUSDT", "direction": "long", "status": "tp2_hit", "result_r": "2", "closed_at": "2026-01-01"}],
    )

    class FakeNotifier:
        def __init__(self) -> None:
            self.message = ""
            self.dry_run = None

        def publish(self, message: str, dry_run: bool = False):
            self.message = message
            self.dry_run = dry_run
            return [{"recipient": "123", "status": "sent", "provider_message_id": "dry_run"}]

    notifier = FakeNotifier()
    results = send_paper_performance_summary(notifier, tmp_path, dry_run=True)

    assert results[0]["status"] == "sent"
    assert notifier.dry_run is True
    assert "📊 Paper Trading Summary" in notifier.message
