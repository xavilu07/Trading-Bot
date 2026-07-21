from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from trading_signals.agents.qic_dashboard import build_qic_control_center


router = APIRouter(prefix="/qic", tags=["qic"])


@router.get("/control-center")
def control_center(limit: int = 50) -> dict[str, Any]:
    return build_qic_control_center(limit=max(1, min(limit, 200)))


@router.get("/status")
def status() -> dict[str, Any]:
    return control_center(limit=20)["status"]


@router.get("/health")
def health() -> dict[str, Any]:
    return _read_report("system_health.json")


@router.get("/agents")
def agents() -> dict[str, Any]:
    return {"agents": control_center()["agents"]}


@router.get("/proposals")
def proposals() -> dict[str, Any]:
    return {"proposals": control_center()["proposals"]}


@router.get("/memory")
def memory() -> dict[str, Any]:
    return control_center()["memory"]


@router.get("/performance")
def performance() -> dict[str, Any]:
    return control_center()["performance"]


@router.get("/events")
def events() -> dict[str, Any]:
    return {"events": control_center()["timeline"]}


@router.get("/changes")
def changes() -> dict[str, Any]:
    return {"changes": control_center()["changes"]}


@router.get("/runs")
def runs() -> dict[str, Any]:
    return {"runs": control_center()["runs"]}


@router.post("/proposals/{proposal_id}/approve")
@router.post("/proposals/{proposal_id}/reject")
@router.post("/proposals/{proposal_id}/revalidate")
@router.post("/changes/{proposal_id}/test")
@router.post("/changes/{proposal_id}/apply")
@router.post("/changes/{proposal_id}/rollback")
def protected_action(proposal_id: str) -> None:
    del proposal_id
    raise HTTPException(status_code=503, detail="QIC actions disabled: secure admin authentication is not configured")


def _read_report(filename: str) -> dict[str, Any]:
    import json

    path = Path("reports") / "qic" / filename
    if not path.exists():
        return {"status": "UNKNOWN", "reason": "report_missing"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "UNHEALTHY", "reason": "report_corrupt"}
    return payload if isinstance(payload, dict) else {"status": "UNKNOWN", "reason": "invalid_report"}
