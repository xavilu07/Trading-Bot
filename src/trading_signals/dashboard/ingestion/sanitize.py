from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Mapping

_SENSITIVE_KEY = re.compile(
    r"(token|secret|password|api[_-]?key|chat[_-]?id|recipient|payload|provider[_-]?message)",
    re.IGNORECASE,
)
_MAX_TEXT_LENGTH = 500


def safe_text(value: object, *, max_length: int = _MAX_TEXT_LENGTH) -> str | None:
    if value is None or not isinstance(value, (str, int, float)):
        return None
    text = str(value)[:max_length]
    lowered = text.lower()
    if (
        text.startswith(("/", "\\"))
        or "/root/" in lowered
        or "/home/" in lowered
        or any(marker in lowered for marker in ("token=", "api_key=", "secret=", "chat_id="))
    ):
        return None
    return text


def safe_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def safe_bool(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    return None


def sanitize_mapping(
    payload: Mapping[str, object],
    *,
    allowed_fields: Iterable[str],
    nested_allowlists: Mapping[str, Iterable[str]] | None = None,
) -> dict[str, object]:
    nested = nested_allowlists or {}
    result: dict[str, object] = {}
    for key in allowed_fields:
        if key not in payload or _SENSITIVE_KEY.search(key):
            continue
        value = payload[key]
        if key in nested and isinstance(value, Mapping):
            result[key] = sanitize_mapping(value, allowed_fields=nested[key])
        elif isinstance(value, (str, int, float, bool)) or value is None:
            cleaned = safe_text(value) if isinstance(value, str) else value
            if cleaned is not None or value is None:
                result[key] = cleaned
        elif isinstance(value, list):
            cleaned_items = [
                item
                for item in value[:100]
                if isinstance(item, (str, int, float, bool)) and safe_text(item) is not None
            ]
            result[key] = cleaned_items
    return result


def sanitized_json(payload: Mapping[str, object], *, allowed_fields: Iterable[str], nested_allowlists=None) -> str:
    cleaned = sanitize_mapping(
        payload,
        allowed_fields=allowed_fields,
        nested_allowlists=nested_allowlists,
    )
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sanitized_error(error: BaseException) -> tuple[str, str]:
    code = str(getattr(error, "code", "PROJECTOR_SOURCE_ERROR"))[:80]
    messages = {
        "SOURCE_CHANGED_DURING_READ": "Source changed during a bounded read.",
        "SOURCE_CORRUPT": "Source content is corrupt.",
        "SOURCE_SCHEMA_INVALID": "Source schema is incompatible.",
        "SOURCE_READ_ERROR": "Source could not be read safely.",
    }
    return code, messages.get(code, "Source projection failed safely.")


def safe_relative_identity(path: Path, root: Path, namespace: str) -> str:
    relative = path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    import hashlib

    return hashlib.sha256(f"{namespace}:{relative}".encode("utf-8")).hexdigest()
