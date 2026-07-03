from __future__ import annotations

import json

from scripts.analyze_signal_update_v1 import build_runtime_diagnostics


def test_build_runtime_diagnostics_counts_signal_update_events(tmp_path) -> None:
    log_file = tmp_path / "scheduler.log"
    events = [
        {"event": "signal_update_v1_detected", "symbol": "BTCUSDT", "direction": "long"},
        {"event": "signal_update_v1_classified", "symbol": "BTCUSDT", "update_type": "STRENGTHENED_SIGNAL"},
        {"event": "signal_update_v1_shadow_decision", "symbol": "BTCUSDT", "update_type": "STRENGTHENED_SIGNAL"},
        {"event": "signal_update_v1_skipped", "symbol": "ETHUSDT", "skip_reason": "active_signal_not_found"},
    ]
    log_file.write_text(
        "\n".join(
            [
                json.dumps(events[0]),
                "2026-07-03 INFO " + json.dumps(events[1]),
                json.dumps(events[2]),
                json.dumps(events[3]),
            ]
        ),
        encoding="utf-8",
    )

    diagnostics = build_runtime_diagnostics(log_file)

    assert diagnostics["detected"] == 1
    assert diagnostics["classified"] == 1
    assert diagnostics["shadow_decision"] == 1
    assert diagnostics["skipped"] == 1
    assert diagnostics["by_update_type"] == {"STRENGTHENED_SIGNAL": 1}
    assert diagnostics["by_skip_reason"] == {"active_signal_not_found": 1}
