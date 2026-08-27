from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

_SENSITIVE_TOKENS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "credential",
    "chat_id",
    "private_key",
)


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(token in normalized for token in _SENSITIVE_TOKENS)


def sanitized_payload(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): sanitized_payload(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if not _sensitive_key(str(key))
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitized_payload(item) for item in value]
    if isinstance(value, str):
        if value.startswith("/") or "/root/" in value.lower():
            return "[REDACTED_PATH]"
        return value[:2_000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:2_000]


def stable_hash(value: object, *, namespace: str) -> str:
    material = f"{namespace}:{canonical_json(sanitized_payload(value))}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def setup_parameters_hash(parameters: Mapping[str, object]) -> str:
    allowed = {
        "atr_min_threshold",
        "entry_timeframe",
        "higher_timeframe",
        "max_distance_to_liquidity_atr",
        "min_body_ratio",
        "min_rr",
        "relaxed_strategy_gates_enabled",
        "setup_score_threshold",
    }
    public = {
        key: value
        for key, value in parameters.items()
        if key in allowed and not _sensitive_key(key)
    }
    return stable_hash(public, namespace="paper_trace_setup_parameters.v1")
