from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_signals.research.adaptive_filter_manager import (
    AdaptiveFilterConfig,
    analyze_adaptive_filter_manager,
    generate_adaptive_filter_manager_report,
    should_block_by_adaptive_filter,
)


NOW = datetime(2026, 6, 8, 12, 0, tzinfo=UTC)


def test_observe_mode_never_changes_runtime_state(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", _toxic_bullish_sweep_rows(30))

    result = generate_adaptive_filter_manager_report(
        data_path=data_path,
        reports_path=tmp_path / "reports",
        runtime_path=tmp_path / "data" / "runtime",
        config=AdaptiveFilterConfig(enabled=True, mode="observe"),
        now=NOW,
    )

    assert "bullish_sweep" in result["adaptive_state"]["proposed_blocks"]
    assert not (tmp_path / "data" / "runtime" / "adaptive_filter_state.json").exists()


def test_shadow_mode_writes_proposals_but_helper_does_not_block(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    runtime_path = tmp_path / "data" / "runtime"
    _write_csv(data_path / "paper_trading" / "trades.csv", _toxic_bullish_sweep_rows(30))

    generate_adaptive_filter_manager_report(
        data_path=data_path,
        reports_path=tmp_path / "reports",
        runtime_path=runtime_path,
        config=AdaptiveFilterConfig(enabled=True, mode="shadow"),
        now=NOW,
    )

    state_path = runtime_path / "adaptive_filter_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert "bullish_sweep" in state["proposed_blocks"]
    assert state["active_blocks"] == []
    assert should_block_by_adaptive_filter(_bullish_eval(), _Settings(mode="shadow"), state_path=state_path, now=NOW)["blocked"] is False


def test_auto_safe_requires_human_approval_false(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", _toxic_bullish_sweep_rows(30))

    result = generate_adaptive_filter_manager_report(
        data_path=data_path,
        reports_path=tmp_path / "reports",
        runtime_path=tmp_path / "data" / "runtime",
        config=AdaptiveFilterConfig(enabled=True, mode="auto_safe", require_human_approval=True),
        now=NOW,
    )

    state = result["adaptive_state"]
    assert "bullish_sweep" in state["proposed_blocks"]
    assert state["active_blocks"] == []
    assert "auto_safe_blocked_by_human_approval_requirement" in state["safety_warnings"]


def test_auto_safe_only_affects_allowed_contexts(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", _toxic_bullish_sweep_rows(30))

    result = analyze_adaptive_filter_manager(
        data_path=data_path,
        config=AdaptiveFilterConfig(
            enabled=True,
            mode="auto_safe",
            require_human_approval=False,
            allowed_contexts=("against_htf_breakout",),
        ),
        now=NOW,
    )

    state = result["adaptive_state"]
    assert "bullish_sweep" in state["proposed_blocks"]
    assert "bullish_sweep" not in state["active_blocks"]
    assert any(str(warning).startswith("proposals_outside_allowed_contexts:") for warning in state["safety_warnings"])


def test_missing_malformed_and_stale_state_fail_open(tmp_path: Path) -> None:
    settings = _Settings()
    missing = tmp_path / "missing.json"
    assert should_block_by_adaptive_filter(_bullish_eval(), settings, state_path=missing, now=NOW)["blocked"] is False

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{bad", encoding="utf-8")
    assert should_block_by_adaptive_filter(_bullish_eval(), settings, state_path=malformed, now=NOW)["blocked"] is False

    stale = tmp_path / "stale.json"
    _write_state(stale, generated_at=NOW - timedelta(hours=25), active_blocks=["bullish_sweep"])
    assert should_block_by_adaptive_filter(_bullish_eval(), settings, state_path=stale, now=NOW)["blocked"] is False


def test_bullish_sweep_toxic_context_recommends_promote_to_block(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", _toxic_bullish_sweep_rows(30))

    result = analyze_adaptive_filter_manager(data_path=data_path, config=AdaptiveFilterConfig(), now=NOW)

    assert result["contexts"]["bullish_sweep"]["recommendation"] == "PROMOTE_TO_BLOCK"


def test_profitable_context_recommends_keep_allowed(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, 1.0, liquidity_sweep="bullish_sweep") for index in range(30)]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_adaptive_filter_manager(data_path=data_path, config=AdaptiveFilterConfig(), now=NOW)

    assert result["contexts"]["bullish_sweep"]["recommendation"] == "KEEP_ALLOWED"


def test_low_sample_recommends_watch(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", _toxic_bullish_sweep_rows(5))

    result = analyze_adaptive_filter_manager(data_path=data_path, config=AdaptiveFilterConfig(), now=NOW)

    assert result["contexts"]["bullish_sweep"]["recommendation"] == "WATCH"


def test_blocked_recovered_context_recommends_unblock_candidate(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, 1.0, liquidity_sweep="bullish_sweep") for index in range(30)]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_adaptive_filter_manager(
        data_path=data_path,
        config=AdaptiveFilterConfig(current_blocks=("bullish_sweep",)),
        now=NOW,
    )

    assert result["contexts"]["bullish_sweep"]["recommendation"] == "UNBLOCK_CANDIDATE"


def test_helper_blocks_only_when_enabled_auto_safe_approved_fresh_and_allowed(tmp_path: Path) -> None:
    state_path = tmp_path / "adaptive_filter_state.json"
    _write_state(state_path, generated_at=NOW, active_blocks=["bullish_sweep"])

    result = should_block_by_adaptive_filter(_bullish_eval(), _Settings(), state_path=state_path, now=NOW)

    assert result == {"blocked": True, "reason": "adaptive_filter:bullish_sweep", "context": "bullish_sweep"}


def test_helper_does_not_block_unknown_contexts(tmp_path: Path) -> None:
    state_path = tmp_path / "adaptive_filter_state.json"
    _write_state(state_path, generated_at=NOW, active_blocks=["unknown_context"])

    result = should_block_by_adaptive_filter(
        _bullish_eval(),
        _Settings(allowed_contexts=("unknown_context",)),
        state_path=state_path,
        now=NOW,
    )

    assert result["blocked"] is False


def test_helper_does_not_block_if_evaluation_does_not_match_context(tmp_path: Path) -> None:
    state_path = tmp_path / "adaptive_filter_state.json"
    _write_state(state_path, generated_at=NOW, active_blocks=["bullish_sweep"])

    result = should_block_by_adaptive_filter(
        {"liquidity_sweep": "bearish_sweep", "market_regime": "RANGING"},
        _Settings(),
        state_path=state_path,
        now=NOW,
    )

    assert result["blocked"] is False


@dataclass(slots=True)
class _Settings:
    adaptive_filter_enabled: bool = True
    adaptive_filter_mode: str = "auto_safe"
    adaptive_filter_require_human_approval: bool = False
    adaptive_filter_allowed_contexts: tuple[str, ...] = ("bullish_sweep", "against_htf_breakout")
    data_storage_path: Path = Path("./data")

    def __init__(
        self,
        *,
        enabled: bool = True,
        mode: str = "auto_safe",
        require_human_approval: bool = False,
        allowed_contexts: tuple[str, ...] = ("bullish_sweep", "against_htf_breakout"),
    ) -> None:
        self.adaptive_filter_enabled = enabled
        self.adaptive_filter_mode = mode
        self.adaptive_filter_require_human_approval = require_human_approval
        self.adaptive_filter_allowed_contexts = allowed_contexts
        self.data_storage_path = Path("./data")


def _bullish_eval() -> dict[str, object]:
    return {"liquidity_sweep": "bullish_sweep", "market_regime": "RANGING", "score": 85}


def _toxic_bullish_sweep_rows(count: int) -> list[dict[str, object]]:
    return [_trade(index, -1.0, liquidity_sweep="bullish_sweep") for index in range(count)]


def _trade(
    index: int,
    result_r: float,
    *,
    symbol: str = "BTCUSDT",
    direction: str = "long",
    session: str = "LONDON",
    regime: str = "RANGING",
    setup: str = "MAIN_SIGNAL",
    entry_context: str = "PULLBACK",
    score: float = 85,
    liquidity_sweep: str = "",
    warnings: str = "",
    penalties: str = "",
    reasons: str = "",
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
        "opened_at": (NOW - timedelta(days=1)).isoformat(),
        "closed_at": (NOW - timedelta(hours=1)).isoformat(),
        "liquidity_sweep": liquidity_sweep,
        "warnings": warnings,
        "penalties": penalties,
        "rejection_reasons": reasons,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_state(path: Path, *, generated_at: datetime, active_blocks: list[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "generated_at": generated_at.isoformat(timespec="seconds"),
                "mode": "auto_safe",
                "enabled": True,
                "active_blocks": active_blocks,
                "proposed_blocks": [],
                "proposed_unblocks": [],
                "contexts": {},
                "safety_warnings": [],
                "human_approval_required": False,
            }
        ),
        encoding="utf-8",
    )
