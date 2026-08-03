from __future__ import annotations

import json
from pathlib import Path

import scripts.run_agent_committee as script


class MinimalSettings:
    data_storage_path = Path("data")
    telegram_bot_token = ""
    telegram_dev_chat_id = ""


class StringFlagSettings(MinimalSettings):
    agent_committee_enabled = "false"
    agent_telegram_approval_enabled = "false"


def test_run_agent_committee_script_tolerates_missing_qic_settings(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run_agent_committee(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "enabled": True,
            "proposal_count": 0,
            "proposal_store": str(tmp_path / "data" / "agent_proposals" / "proposals.jsonl"),
            "telegram_results": [],
        }

    monkeypatch.setattr(script, "load_settings", lambda: MinimalSettings())
    monkeypatch.setattr(script, "run_agent_committee", fake_run_agent_committee)
    # resolve_qic_telegram_config() now resolves token/chat via load_qic_telegram_config()
    # (single source of truth shared with the listener) instead of reading it off the
    # settings object, so "missing qic settings" must be simulated there, not on Settings.
    monkeypatch.setattr(
        "trading_signals.agents.telegram_approval.load_qic_telegram_config",
        lambda: {
            "enabled": False,
            "configured": False,
            "bot_token": "",
            "chat_id": "",
            "chat_ids": [],
            "source": "missing",
        },
    )

    rc = script.main(
        [
            "--reports-root",
            str(tmp_path / "reports"),
            "--output-path",
            str(tmp_path / "reports" / "qic"),
            "--force",
            "--dry-run",
            "--min-confidence",
            "LOW",
        ]
    )

    assert rc == 0
    assert captured["enabled"] is False
    assert captured["min_confidence"] == "LOW"
    assert captured["telegram_enabled"] is False
    assert captured["telegram_bot_token"] == ""
    assert captured["telegram_chat_id"] == ""


def test_run_agent_committee_script_parses_string_flags(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run_agent_committee(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "enabled": True,
            "proposal_count": 0,
            "proposal_store": str(tmp_path / "data" / "agent_proposals" / "proposals.jsonl"),
            "telegram_results": [],
        }

    monkeypatch.setattr(script, "load_settings", lambda: StringFlagSettings())
    monkeypatch.setattr(script, "run_agent_committee", fake_run_agent_committee)

    rc = script.main(
        [
            "--reports-root",
            str(tmp_path / "reports"),
            "--output-path",
            str(tmp_path / "reports" / "qic"),
            "--dry-run",
        ]
    )

    assert rc == 0
    assert captured["enabled"] is False
    assert captured["telegram_enabled"] is False


def test_run_agent_committee_script_overwrites_reports_on_failure(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "reports" / "qic"
    output_path.mkdir(parents=True)
    for name in ("debate", "consensus", "proposal", "agent_memory"):
        (output_path / f"{name}.json").write_text(json.dumps({"status": "old"}), encoding="utf-8")
        (output_path / f"{name}.md").write_text("old report", encoding="utf-8")

    def failing_committee(**_: object) -> dict[str, object]:
        raise RuntimeError("committee failed")

    monkeypatch.setattr(script, "load_settings", lambda: MinimalSettings())
    monkeypatch.setattr(script, "run_agent_committee", failing_committee)

    rc = script.main(
        [
            "--reports-root",
            str(tmp_path / "reports"),
            "--output-path",
            str(output_path),
            "--force",
            "--dry-run",
        ]
    )

    assert rc == 1
    for name in ("debate", "consensus", "proposal", "agent_memory"):
        payload = json.loads((output_path / f"{name}.json").read_text(encoding="utf-8"))
        assert payload["status"] == "failed"
        assert payload["error"] == "committee failed"
        assert "Status: failed" in (output_path / f"{name}.md").read_text(encoding="utf-8")
