from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_research_reports(reports_root: Path = Path("reports")) -> dict[str, Any]:
    return {
        "historical_intelligence": _load_dir(reports_root / "historical_intelligence"),
        "quant_research": _load_dir(reports_root / "quant_research"),
        "strategy_simulator": _load_dir(reports_root / "strategy_simulator"),
    }


def generate_research_proposals(reports: dict[str, Any]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    quant_candidates = _list(
        reports.get("quant_research", {})
        .get("strategy_v2_candidates", {})
        .get("candidates", [])
    )
    for candidate in quant_candidates[:20]:
        proposals.append(
            {
                "source_agent": "research_agent",
                "title": f"Research candidate: {candidate.get('action', 'Review context')}",
                "hypothesis": str(candidate.get("rationale") or "Quant research found a context worth reviewing."),
                "expected_pf": None,
                "expected_total_r": _float(candidate.get("expected_improvement")),
                "trades_lost": int(float(candidate.get("trades_affected") or 0)),
                "confidence": str(candidate.get("confidence") or "LOW").upper(),
                "risk_level": "MEDIUM",
                "evidence": int(float(candidate.get("evidence") or 0)),
                "context": candidate.get("context") or {},
            }
        )
    recommendations = _list(
        reports.get("historical_intelligence", {})
        .get("recommendations", {})
        .get("recommendations", [])
    )
    for item in recommendations[:20]:
        proposals.append(
            {
                "source_agent": "research_agent",
                "title": f"Historical intelligence: {item.get('action') or item.get('recommendation') or 'Review edge'}",
                "hypothesis": str(item.get("rationale") or item.get("expected_impact") or "Historical report generated a recommendation."),
                "expected_pf": None,
                "expected_total_r": _float(item.get("expected_impact")),
                "trades_lost": int(float(item.get("trades_affected") or 0)),
                "confidence": str(item.get("confidence") or "LOW").upper(),
                "risk_level": "LOW",
                "evidence": int(float(item.get("evidence") or 0)),
                "context": item.get("context") or {},
            }
        )
    return proposals


def _load_dir(path: Path) -> dict[str, Any]:
    output: dict[str, Any] = {}
    if not path.exists():
        return output
    for item in path.glob("*.json"):
        try:
            output[item.stem] = json.loads(item.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            output[item.stem] = {"error": "invalid_json", "path": str(item)}
    return output


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None
