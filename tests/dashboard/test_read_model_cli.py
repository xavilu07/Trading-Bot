from __future__ import annotations

import json
from pathlib import Path

from trading_signals.dashboard.cli import main


def _base_args(tmp_path: Path) -> list[str]:
    return [
        "--sqlite-path",
        str(tmp_path / "runtime/read-model.sqlite"),
        "--bot-root",
        str(tmp_path),
        "--data-root",
        str(tmp_path / "data"),
        "--reports-root",
        str(tmp_path / "reports"),
        "--runtime-root",
        str(tmp_path / "runtime"),
    ]


def test_cli_migrate_project_inspect_and_rebuild_are_finite(
    tmp_path: Path,
    capsys,
) -> None:
    heartbeat = tmp_path / "data/runtime/scheduler_heartbeat.json"
    heartbeat.parent.mkdir(parents=True)
    heartbeat.write_text(
        json.dumps(
            {
                "status": "ok",
                "cycle_number": 1,
                "last_cycle_finished_at": "2026-07-28T10:00:00+00:00",
                "git_commit_sha": "a" * 40,
                "selected_engine": "legacy",
                "strategy_version": "v1",
                "policy_version": "v1",
            }
        ),
        encoding="utf-8",
    )
    assert main(["migrate", *_base_args(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert main(["project-once", *_base_args(tmp_path), "--sources", "scheduler_heartbeat"]) == 0
    project_output = json.loads(capsys.readouterr().out)
    assert project_output["summary"]["totals"]["records_written"] == 1
    assert main(["inspect", *_base_args(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ready"
    assert main(["rebuild", *_base_args(tmp_path), "--sources", "scheduler_heartbeat"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_cli_inspect_missing_is_read_only(tmp_path: Path, capsys) -> None:
    target = tmp_path / "runtime/read-model.sqlite"
    assert main(["inspect", *_base_args(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "missing"
    assert not target.exists()
    assert not target.parent.exists()


def test_cli_rejects_unknown_sources_and_dangerous_paths(tmp_path: Path, capsys) -> None:
    assert main(["migrate", *_base_args(tmp_path), "--sources", "paper_trades"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    dangerous = _base_args(tmp_path)
    sqlite_index = dangerous.index("--sqlite-path") + 1
    dangerous[sqlite_index] = str(tmp_path / "data/read-model.sqlite")
    assert main(["migrate", *dangerous]) == 2
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "error"
    assert not (tmp_path / "data/read-model.sqlite").exists()


def test_cli_outcomes_once_and_inspect_outcome_are_finite(
    tmp_path: Path,
    capsys,
) -> None:
    signal = tmp_path / "data/trade_signals/2026-07-28/sig-one.json"
    signal.parent.mkdir(parents=True)
    signal.write_text(
        json.dumps(
            {
                "id": "sig-one",
                "risk_plan_id": "risk-one",
                "symbol": "BTCUSDT",
                "decision": "long",
                "status": "valid",
                "entry_timeframe": "1h",
                "created_at": "2026-07-28T10:15:00+00:00",
                "strategy_version": "v1",
            }
        ),
        encoding="utf-8",
    )
    risk = tmp_path / "data/risk_plans/2026-07-28/risk-one.json"
    risk.parent.mkdir(parents=True)
    risk.write_text(
        json.dumps(
            {
                "id": "risk-one",
                "entry": 100,
                "stop_loss": 95,
                "take_profit": 110,
            }
        ),
        encoding="utf-8",
    )
    market = tmp_path / "data/market_snapshots/2026-07-28/snapshot.json"
    market.parent.mkdir(parents=True)
    market.write_text(
        json.dumps(
            {
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "timestamp": "2026-07-28T11:59:59.999000+00:00",
                "open": 100,
                "high": 111,
                "low": 99,
                "close": 110,
            }
        ),
        encoding="utf-8",
    )
    args = _base_args(tmp_path)
    assert main(["migrate", *args]) == 0
    capsys.readouterr()
    assert main(["project-once", *args, "--sources", "trade_signals"]) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "outcomes-once",
                *args,
                "--horizon-candles",
                "1",
                "--as-of",
                "2026-07-28T13:00:00+00:00",
            ]
        )
        == 0
    )
    outcome = json.loads(capsys.readouterr().out)
    assert outcome["summary"]["status_counts"] == {"WIN": 1}
    database = tmp_path / "runtime/read-model.sqlite"
    before = database.read_bytes()
    assert main(["inspect-outcome", *args, "--signal-key", "sig-one"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["status"] == "ok"
    assert database.read_bytes() == before
