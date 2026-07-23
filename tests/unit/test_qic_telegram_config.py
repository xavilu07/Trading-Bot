from __future__ import annotations

import json
from pathlib import Path

from scripts.configure_qic_telegram import validate_telegram_config, write_config
from scripts.run_qic_telegram_listener import main as listener_main
from trading_signals.agents.qic_telegram_config import load_qic_telegram_config, mask_token


def test_config_loader_prefers_exported_env(tmp_path: Path) -> None:
    config = load_qic_telegram_config(
        env_file=tmp_path / ".env",
        config_path=tmp_path / "qic_telegram.json",
        environ={"QIC_TELEGRAM_BOT_TOKEN": "env-token", "QIC_TELEGRAM_CHAT_ID": "111"},
    )

    assert config["enabled"] is True
    assert config["bot_token"] == "env-token"
    assert config["chat_ids"] == ["111"]
    assert config["source"] == "env:qic"


def test_config_loader_reads_dotenv_before_json(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("QIC_TELEGRAM_BOT_TOKEN=dotenv-token\nQIC_TELEGRAM_CHAT_ID=222\n", encoding="utf-8")
    json_path = tmp_path / "qic_telegram.json"
    json_path.write_text(json.dumps({"bot_token": "json-token", "chat_ids": ["333"]}), encoding="utf-8")

    config = load_qic_telegram_config(env_file=env_file, config_path=json_path, environ={})

    assert config["bot_token"] == "dotenv-token"
    assert config["chat_ids"] == ["222"]
    assert config["source"] == "dotenv:qic"


def test_config_loader_reads_json_config_and_multiple_chat_ids(tmp_path: Path) -> None:
    json_path = tmp_path / "config" / "qic_telegram.json"
    json_path.parent.mkdir()
    json_path.write_text(json.dumps({"bot_token": "json-token", "chat_ids": [111, "222", "222"]}), encoding="utf-8")

    config = load_qic_telegram_config(env_file=tmp_path / ".env", config_path=json_path, environ={})

    assert config["configured"] is True
    assert config["chat_ids"] == ["111", "222"]
    assert config["chat_id"] == "111,222"
    assert config["source"].startswith("json:")


def test_config_loader_fallback_to_telegram_dev(tmp_path: Path) -> None:
    config = load_qic_telegram_config(
        env_file=tmp_path / ".env",
        config_path=tmp_path / "missing.json",
        environ={"TELEGRAM_BOT_TOKEN": "fallback-token", "TELEGRAM_DEV_CHAT_ID": "444,555"},
    )

    assert config["bot_token"] == "fallback-token"
    assert config["chat_ids"] == ["444", "555"]
    assert config["source"] == "fallback:telegram_dev"


def test_mask_token_never_exposes_full_token() -> None:
    assert mask_token("123456789:E2A").endswith("E2A")
    assert "123456789" not in mask_token("123456789:E2A")


def test_invalid_token_validation_reports_failed(monkeypatch) -> None:
    def fake_urlopen(*args: object, **kwargs: object) -> object:
        raise OSError("invalid token")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = validate_telegram_config(bot_token="bad-token", chat_id="123")

    assert result["get_me"]["status"] == "failed"
    assert result["send_message"]["status"] == "failed"


def test_write_config_uses_secure_permissions(tmp_path: Path) -> None:
    path = tmp_path / "config" / "qic_telegram.json"

    write_config({"bot_token": "token", "chat_ids": ["123"]}, path)

    assert json.loads(path.read_text(encoding="utf-8"))["bot_token"] == "token"
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_listener_startup_processes_callbacks_without_network(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QIC_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("QIC_TELEGRAM_CHAT_ID", "123")

    def fake_poll(**kwargs: object) -> dict[str, object]:
        return {
            "status": "ok",
            "processed": [
                {"action": "history", "proposal_id": "prop_1", "status": "history_loaded"},
            ],
        }

    monkeypatch.setattr("scripts.run_qic_telegram_listener.poll_approval_callbacks", fake_poll)

    code = listener_main(
        [
            "--once",
            "--dry-run",
            "--reports-path",
            str(tmp_path / "reports" / "qic"),
            "--lock-path",
            str(tmp_path / "data" / "qic" / "locks" / "telegram_listener.lock"),
            "--offset-path",
            str(tmp_path / "data" / "qic" / "telegram_update_offset.json"),
            "--callback-history-path",
            str(tmp_path / "data" / "qic" / "telegram_callbacks.jsonl"),
        ]
    )

    assert code == 0
    report = json.loads((tmp_path / "reports" / "qic" / "telegram_listener.json").read_text(encoding="utf-8"))
    assert report["callbacks_processed"] == 1
    assert report["last_callback"]["action"] == "history"
