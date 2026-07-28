from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

FROZEN_POLICY_VERSION = "closed-bars-entry-touch-v1"
FROZEN_ENGINE_VERSION = "canonical-outcomes.v1"
METRIC_DEFINITION_VERSION = "canonical-metrics.v1"
BOOTSTRAP_SEED_VERSION = "canonical-metrics-bootstrap.v1:20260728"


def _policy_path() -> Path:
    return Path(__file__).resolve().parent / "policies" / f"{FROZEN_POLICY_VERSION}.json"


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def frozen_policy_specification() -> Mapping[str, object]:
    payload = json.loads(_policy_path().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("FROZEN_POLICY_SPEC_INVALID")
    if payload.get("policy_version") != FROZEN_POLICY_VERSION:
        raise RuntimeError("FROZEN_POLICY_VERSION_MISMATCH")
    if payload.get("engine_version") != FROZEN_ENGINE_VERSION:
        raise RuntimeError("FROZEN_ENGINE_VERSION_MISMATCH")
    return payload


def frozen_policy_checksum() -> str:
    encoded = canonical_json(frozen_policy_specification()).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
