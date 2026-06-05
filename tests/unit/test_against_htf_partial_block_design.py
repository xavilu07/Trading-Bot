from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.against_htf_partial_block_design import (
    analyze_against_htf_partial_block_design,
    classify_candidate,
    write_against_htf_partial_block_design_report,
)


def test_partial_block_evaluates_all_candidate_filters(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, -1.0, session="ASIA", warnings="against_htf|low_volume", entry_context="BREAKOUT"),
            _trade(2, -1.0, session="ASIA", warnings="against_htf", entry_context="PULLBACK"),
            _trade(3, 1.0, session="LONDON", warnings="against_htf", entry_context="PULLBACK"),
            _trade(4, -1.0, session="LONDON", warnings="against_htf|low_volume", entry_context="BREAKOUT", setup="SECONDARY_SIGNAL"),
        ],
    )

    result = analyze_against_htf_partial_block_design(data_path=data_path)

    assert len(result["candidate_results"]) == 7
    assert {row["candidate"] for row in result["candidate_results"]} == {
        "against_htf AND session=ASIA",
        "against_htf AND low_volume",
        "against_htf AND BREAKOUT",
        "against_htf AND SECONDARY_SIGNAL",
        "against_htf AND ASIA AND low_volume",
        "against_htf AND ASIA AND BREAKOUT",
        "against_htf AND low_volume AND BREAKOUT",
    }


def test_partial_block_ranks_best_candidate_by_pf_and_r_improvement(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, -1.0, session="ASIA", warnings="against_htf|low_volume", entry_context="BREAKOUT") for index in range(8)]
    rows.extend(_trade(index + 20, 1.0, session="LONDON", warnings="against_htf", entry_context="PULLBACK") for index in range(8))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_against_htf_partial_block_design(data_path=data_path)

    assert result["filter_ranking"][0]["candidate"] in {
        "against_htf AND session=ASIA",
        "against_htf AND low_volume",
        "against_htf AND BREAKOUT",
        "against_htf AND ASIA AND low_volume",
        "against_htf AND ASIA AND BREAKOUT",
        "against_htf AND low_volume AND BREAKOUT",
    }
    assert result["filter_ranking"][0]["r_improvement"] == 8.0
    assert result["filter_ranking"][0]["profitable_trades_lost"] == 0
    assert "Shadow-test" in result["recommended_next_action"]


def test_partial_block_tracks_collateral_damage(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, -1.0, session="ASIA", warnings="against_htf"),
            _trade(2, 1.0, session="ASIA", warnings="against_htf"),
            _trade(3, 1.0, session="LONDON", warnings="against_htf"),
        ],
    )

    result = analyze_against_htf_partial_block_design(data_path=data_path)
    asia = next(row for row in result["candidate_results"] if row["candidate"] == "against_htf AND session=ASIA")

    assert asia["trades_removed"] == 2
    assert asia["profitable_trades_lost"] == 1
    assert asia["losing_trades_removed"] == 1


def test_partial_block_ignores_bullish_sweep_rows(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, -1.0, session="ASIA", warnings="against_htf", liquidity_sweep="bullish_sweep"),
            _trade(2, -1.0, session="ASIA", warnings="against_htf"),
        ],
    )

    result = analyze_against_htf_partial_block_design(data_path=data_path)
    asia = next(row for row in result["candidate_results"] if row["candidate"] == "against_htf AND session=ASIA")

    assert result["baseline_metrics"]["trades"] == 1
    assert asia["trades_removed"] == 1


def test_partial_block_classifies_candidates() -> None:
    assert classify_candidate({"trades_removed": 0, "r_improvement": 0.0, "pf_improvement": 0.0}) == "REJECT"
    assert (
        classify_candidate(
            {
                "trades_removed": 25,
                "r_improvement": 6.0,
                "pf_improvement": 0.2,
                "profitable_trades_lost": 5,
                "losing_trades_removed": 20,
            }
        )
        == "DEPLOY"
    )
    assert (
        classify_candidate(
            {
                "trades_removed": 5,
                "r_improvement": 1.0,
                "pf_improvement": 0.1,
                "profitable_trades_lost": 2,
                "losing_trades_removed": 3,
            }
        )
        == "SHADOW_TEST"
    )


def test_partial_block_report_is_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, -1.0, session="ASIA", warnings="against_htf")])

    result = analyze_against_htf_partial_block_design(data_path=data_path)
    path = write_against_htf_partial_block_design_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "AGAINST_HTF_PARTIAL_BLOCK_DESIGN" in text
    assert "Filter Ranking" in text
    assert "Recommended Next Action" in text


def _trade(
    index: int,
    result_r: float,
    *,
    symbol: str = "BTCUSDT",
    direction: str = "long",
    session: str = "LONDON",
    regime: str = "TRENDING",
    setup: str = "MAIN_SIGNAL",
    score: float = 85,
    entry_context: str = "PULLBACK",
    liquidity_sweep: str = "",
    warnings: str = "",
    penalties: str = "",
    trend_higher: str = "",
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": setup,
        "market_regime": regime,
        "session": session,
        "entry_context": entry_context,
        "trade_location": "mid_range",
        "score": score,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
        "liquidity_sweep": liquidity_sweep,
        "warnings": warnings,
        "penalties": penalties,
        "trend_higher": trend_higher,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
