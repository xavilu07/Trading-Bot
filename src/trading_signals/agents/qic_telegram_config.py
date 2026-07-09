from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

DEFAULT_QIC_TELEGRAM_CONFIG_PATH = Path("config") / "qic_telegram.json"
DEFAULT_ENV_FILE = Path(".env")


def load_qic_telegram_config(
    *,
    env_file: Path = DEFAULT_ENV_FILE,
    config_path: Path = DEFAULT_QIC_TELEGRAM_CONFIG_PATH,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = dict(os.environ if environ is None else environ)
    dotenv = _load_dotenv_values(env_file)

    token = env.get("QIC_TELEGRAM_BOT_TOKEN")
    chat_ids = _parse_chat_ids(env.get("QIC_TELEGRAM_CHAT_ID"))
    if token and chat_ids:
        return _result(token, chat_ids, "env:qic")

    token = dotenv.get("QIC_TELEGRAM_BOT_TOKEN")
    chat_ids = _parse_chat_ids(dotenv.get("QIC_TELEGRAM_CHAT_ID"))
    if token and chat_ids:
        return _result(token, chat_ids, "dotenv:qic")

    json_config = _load_json_config(config_path)
    token = str(json_config.get("bot_token") or "")
    chat_ids = _parse_chat_ids(json_config.get("chat_ids") or json_config.get("chat_id"))
    if token and chat_ids:
        return _result(token, chat_ids, f"json:{config_path}")

    token = env.get("TELEGRAM_BOT_TOKEN") or dotenv.get("TELEGRAM_BOT_TOKEN")
    chat_ids = _parse_chat_ids(env.get("TELEGRAM_DEV_CHAT_ID") or dotenv.get("TELEGRAM_DEV_CHAT_ID"))
    if token and chat_ids:
        return _result(token, chat_ids, "fallback:telegram_dev")

    return {
        "enabled": False,
        "configured": False,
        "bot_token": "",
        "chat_ids": [],
        "chat_id": "",
        "source": "missing",
        "masked_bot_token": "",
    }


def mask_token(token: str) -> str:
    if not token:
        return ""
    suffix = token[-3:] if len(token) >= 3 else token
    return "*" * max(len(token) - len(suffix), 3) + suffix


def _result(token: str, chat_ids: list[str], source: str) -> dict[str, Any]:
    chat_id = ",".join(chat_ids)
    return {
        "enabled": True,
        "configured": True,
        "bot_token": token,
        "chat_ids": chat_ids,
        "chat_id": chat_id,
        "source": source,
        "masked_bot_token": mask_token(token),
    }


def _load_dotenv_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _load_json_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _parse_chat_ids(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        raw_values = value
    else:
        raw_values = str(value).split(",")
    output = []
    for item in raw_values:
        chat_id = str(item).strip()
        if chat_id and chat_id not in output:
            output.append(chat_id)
    return output
