from __future__ import annotations

import json
from pathlib import Path

from trading_signals.application.use_cases.relaxation_shadow_v1 import RelaxationShadowV1Store
from trading_signals.application.use_cases.relaxation_shadow_v2 import (
    build_relaxation_shadow_v2_intelligence,
    write_relaxation_shadow_v2_reports,
)


def test_relaxation_shadow_v2_empty_dataset_does_not_break(tmp_path: Path) -> None:
    result = build_relaxation_shadow_v2_intelligence(data_path=tmp_path, min_trades=5)

    assert result["records_analyzed"] == 0
    assert result["closed_trades"] == 0
    assert result["overall_metrics"]["total_r"] == 0


def test_relaxation_shadow_v2_classifies_safe_need_more_and_toxic(tmp_path: Path) -> None:
    store = RelaxationShadowV1Store(tmp_path)
    rows = []
    rows.extend(_trade("BTCUSDT", "breakout_bad_location", result_r=1.0, session="OVERLAP") for _ in range(5))
    rows.extend(_trade("ETHUSDT", "against_htf", result_r=-1.0, session="LONDON") for _ in range(5))
    rows.extend(_trade("SOLUSDT", "market_regime_ranging", result_r=1.0, session="NEW_YORK") for _ in range(2))
    store.save_trades(rows)

    result = build_relaxation_shadow_v2_intelligence(data_path=tmp_path, min_trades=5)
    by_filter = {
        row["value"]: row["classification"]
        for row in result["analyses"]["performance_by_relaxed_filter"]
    }

    assert by_filter["breakout_bad_location"] == "SAFE_TO_RELAX"
    assert by_filter["against_htf"] == "TOXIC_TO_RELAX"
    assert by_filter["market_regime_ranging"] == "NEED_MORE_DATA"


def test_relaxation_shadow_v2_includes_required_dimensions(tmp_path: Path) -> None:
    store = RelaxationShadowV1Store(tmp_path)
    store.save_trades([
        _trade("BTCUSDT", "breakout_bad_location", result_r=1.0, session="OVERLAP", score=82, direction="long"),
        _trade("ETHUSDT", "against_htf", result_r=-1.0, session="LONDON", score=55, direction="short"),
    ])

    result = build_relaxation_shadow_v2_intelligence(data_path=tmp_path, min_trades=1)
    analyses = result["analyses"]

    assert analyses["filter_combinations"]
    assert analyses["performance_by_session"]
    assert analyses["performance_by_market_regime"]
    assert analyses["performance_by_setup_type"]
    assert analyses["performance_by_score_bucket"]
    assert analyses["performance_by_direction"]
    assert analyses["performance_by_symbol"]


def test_relaxation_shadow_v2_writes_reports(tmp_path: Path) -> None:
    store = RelaxationShadowV1Store(tmp_path)
    store.save_trades([_trade("BTCUSDT", "breakout_bad_location", result_r=1.0)])

    result = build_relaxation_shadow_v2_intelligence(data_path=tmp_path, min_trades=1)
    paths = write_relaxation_shadow_v2_reports(result, tmp_path / "reports")

    assert paths["markdown_path"].exists()
    assert paths["json_path"].exists()
    payload = json.loads(paths["json_path"].read_text(encoding="utf-8"))
    assert payload["dataset"] == "data/shadow_relaxation/trades.csv"


def _trade(
    symbol: str,
    relaxed_filter: str,
    *,
    result_r: float,
    session: str = "OVERLAP",
    score: float = 80,
    direction: str = "long",
) -> dict[str, object]:
    return {
        "trade_id": f"relax_{symbol}_{relaxed_filter}_{result_r}",
        "dedupe_key": f"{symbol}|{direction}|{relaxed_filter}|{result_r}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": "MAIN_SIGNAL",
        "score": score,
        "entry_price": 100,
        "stop_loss": 95 if direction == "long" else 105,
        "take_profit_1": 105 if direction == "long" else 95,
        "take_profit_2": 110 if direction == "long" else 90,
        "risk_reward_tp1": 1,
        "risk_reward_tp2": 2,
        "opened_at": "2026-01-01T10:00:00+00:00",
        "updated_at": "2026-01-01T11:00:00+00:00",
        "closed_at": "2026-01-01T11:00:00+00:00",
        "expires_after_candles": 24,
        "candles_held": 1,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "mfe_r": max(result_r, 0),
        "mae_r": min(result_r, 0),
        "session": session,
        "market_regime": "TRENDING",
        "entry_context": "BREAKOUT",
        "trade_location": "mid_range",
        "market_structure": "bullish",
        "liquidity_sweep": "bullish_sweep",
        "trend_1h": "bullish",
        "trend_4h": "bullish",
        "rr_valid": True,
        "relaxed_filters": json.dumps([relaxed_filter]),
        "original_rejection_reasons": json.dumps([relaxed_filter]),
        "relaxed_reasons": json.dumps(["safe_to_relax_filters_only"]),
        "context": "{}",
    }
