from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from trading_signals.paper_trace.sanitize import stable_hash

DEFAULT_FILL_POLICY_ID = "paper-closed-bar-touch-modeled-fill-v1"
DEFAULT_EXPIRY_POLICY_ID = "position-expired-unresolved-v1"
TRACE_MODEL_VERSION = "prospective-paper-trace-engine.v1"


def _policy_path() -> Path:
    return Path(__file__).resolve().parent / "policies" / f"{DEFAULT_FILL_POLICY_ID}.json"


def trace_policy_specification() -> Mapping[str, object]:
    payload = json.loads(_policy_path().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("TRACE_POLICY_SPEC_INVALID")
    expected = {
        "fill_policy_id": DEFAULT_FILL_POLICY_ID,
        "expiry_policy_id": DEFAULT_EXPIRY_POLICY_ID,
        "model_version": TRACE_MODEL_VERSION,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise RuntimeError("TRACE_POLICY_IDENTITY_MISMATCH")
    return payload


def trace_policy_checksum() -> str:
    return stable_hash(
        trace_policy_specification(),
        namespace="paper_trace_policy.v1",
    )
