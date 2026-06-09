from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path

from trading_signals.research import elite_profile_c_shadow_tracker
from trading_signals.research.elite_profile_c_shadow_tracker import (
    analyze_elite_profile_c_shadow_tracker,
    generate_elite_profile_c_shadow_tracker,
    matches_elite_profile_c,
    recommend_elite_profile_c,
)


def test_profile_c_match_logic_requires_secondary_score_90_and_aligned_htf() -> None:
    assert matches_elite_profile_c(_trade(1, "BTCUSDT", "short", 1.0, setup="SECONDARY_SIGNAL", score=90, trend_higher="bearish"))
    assert not matches_elite_profile_c(_trade(2, "BTCUSDT", "short", 1.0, setup="MAIN_SIGNAL", score=90, trend_higher="bearish"))
    assert not matches_elite_profile_c(_trade(3, "BTCUSDT", "short", 1.0, setup="SECONDARY_SIGNAL", score=89.9, trend_higher="bearish"))
    assert not matches_elite_profile_c(_trade(4, "BTCUSDT", "short", 1.0, setup="SECONDARY_SIGNAL", score=90, trend_higher="bullish"))


def test_tracker_reads_canonical_trades_and_computes_metrics(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "SOLUSDT", "short", 1.0, setup="SECONDARY_SIGNAL", score=95, trend_higher="bearish") for index in range(6)]
    rows.extend(_trade(index + 10, "ETHUSDT", "short", -1.0, setup="SECONDARY_SIGNAL", score=95, trend_higher="bearish") for index in range(4))
    rows.extend(_trade(index + 20, "BTCUSDT", "short", 1.0, setup="MAIN_SIGNAL", score=95, trend_higher="bearish") for index in range(3))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_elite_profile_c_shadow_tracker(data_path=data_path)

    assert result["total_tracked"] == 10
    assert result["closed_evaluable"] == 10
    assert result["metrics"]["winrate"] == 60.0
    assert result["metrics"]["profit_factor"] == 1.5
    assert result["by_symbol"]["SOLUSDT"]["closed"] == 6
    assert "BTCUSDT" not in result["by_symbol"]


def test_tracker_reads_signal_log_candidates(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            {
                "timestamp": "2026-06-01T12:00:00+00:00",
                "symbol": "AAVEUSDT",
                "direction": "short",
                "setup_type": "SECONDARY_SIGNAL",
                "score": 91,
                "trend_higher": "bearish",
                "session": "LONDON",
            },
            {
                "timestamp": "2026-06-01T12:01:00+00:00",
                "symbol": "BTCUSDT",
                "direction": "short",
                "setup_type": "SECONDARY_SIGNAL",
                "score": 88,
                "trend_higher": "bearish",
            },
        ],
    )

    result = analyze_elite_profile_c_shadow_tracker(data_path=data_path)

    assert result["total_tracked"] == 1
    assert result["records"][0]["source"] == "signals_log"
    assert result["records"][0]["symbol"] == "AAVEUSDT"
    assert result["records"][0]["score_bucket"] == "90+"


def test_generate_writes_shadow_csv_and_report(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "SOLUSDT", "short", 1.0, setup="SECONDARY_SIGNAL", score=95, trend_higher="bearish")])

    result = generate_elite_profile_c_shadow_tracker(data_path=data_path, reports_path=reports_path, dev_note_enabled=True)

    csv_path = Path(result["shadow_csv_path"])
    report_path = Path(result["report_path"])
    assert csv_path.exists()
    assert report_path.exists()
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8", newline="")))
    assert rows[0]["symbol"] == "SOLUSDT"
    assert rows[0]["setup_type"] == "SECONDARY_SIGNAL"
    assert "ELITE_PROFILE_C_SHADOW_TRACKER" in report_path.read_text(encoding="utf-8")
    assert result["dev_note_enabled"] is True


def test_recommendation_rules() -> None:
    assert recommend_elite_profile_c({"trades": 42, "winrate": 59.5, "profit_factor": 2.64, "total_r": 10.5}) == "PROMOTE_TO_PRIORITY"
    assert recommend_elite_profile_c({"trades": 20, "winrate": 50, "profit_factor": 1.6, "total_r": 3}) == "PROMOTE_TO_PUBLIC_TAG"
    assert recommend_elite_profile_c({"trades": 10, "winrate": 50, "profit_factor": 1.2, "total_r": 1}) == "KEEP_SHADOW"
    assert recommend_elite_profile_c({"trades": 10, "winrate": 30, "profit_factor": 0.8, "total_r": -1}) == "REJECT_PROFILE"


def test_tracker_does_not_touch_public_sending() -> None:
    source = inspect.getsource(elite_profile_c_shadow_tracker)

    assert "publish_signal" not in source
    assert "telegram" not in source.lower()
    assert "public_published" not in source


def _trade(
    index: int,
    symbol: str,
    direction: str,
    result_r: float,
    *,
    setup: str = "SECONDARY_SIGNAL",
    score: float = 95,
    trend_higher: str = "bearish",
    session: str = "LONDON",
    regime: str = "TRENDING",
    entry_context: str = "PULLBACK",
    liquidity_sweep: str = "bearish_sweep",
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": setup,
        "score": score,
        "trend_higher": trend_higher,
        "session": session,
        "market_regime": regime,
        "entry_context": entry_context,
        "trade_location": "premium_zone",
        "liquidity_sweep": liquidity_sweep,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
