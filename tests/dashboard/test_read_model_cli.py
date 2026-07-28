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
