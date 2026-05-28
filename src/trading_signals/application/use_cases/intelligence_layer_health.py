from __future__ import annotations

import json
from pathlib import Path


def build_intelligence_layer_health(reports_path: Path = Path("reports")) -> dict[str, object]:
    manifest_path = reports_path / "intelligence_layer_manifest.json"
    if not manifest_path.exists():
        return _empty_health("error", ["missing_manifest"], manifest_path)
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_health("error", ["invalid_manifest"], manifest_path)
    if not isinstance(raw, dict):
        return _empty_health("error", ["invalid_manifest"], manifest_path)

    rows = raw.get("rows", {})
    if not isinstance(rows, dict):
        rows = {}
    missing = raw.get("warnings", [])
    if not isinstance(missing, list):
        missing = []
    status = "OK" if not missing else "warning"
    return {
        "status": status,
        "generated_at": raw.get("generated_at"),
        "closed_trades_analyzed": _int(rows.get("closed_trades")),
        "outcome_rows": _int(rows.get("outcome_intelligence")),
        "setup_ranking_rows": _int(rows.get("setup_rankings")),
        "edge_breakdown_rows": _int(rows.get("edge_breakdown")),
        "missing_required_reports": [str(item) for item in missing],
        "manifest_path": str(manifest_path),
    }


def format_intelligence_layer_health_for_telegram(health: dict[str, object]) -> str:
    missing = health.get("missing_required_reports", [])
    missing_count = len(missing) if isinstance(missing, list) else 0
    return (
        "🧠 Intelligence Layer\n"
        f"- Status: {health.get('status', 'error')}\n"
        f"- Generated: {health.get('generated_at') or 'N/A'}\n"
        f"- Closed trades: {health.get('closed_trades_analyzed', 0)}\n"
        f"- Outcome rows: {health.get('outcome_rows', 0)}\n"
        f"- Setup rankings: {health.get('setup_ranking_rows', 0)}\n"
        f"- Edge breakdown: {health.get('edge_breakdown_rows', 0)}\n"
        f"- Missing required: {missing_count}"
    )


def _empty_health(status: str, missing: list[str], manifest_path: Path) -> dict[str, object]:
    return {
        "status": status,
        "generated_at": None,
        "closed_trades_analyzed": 0,
        "outcome_rows": 0,
        "setup_ranking_rows": 0,
        "edge_breakdown_rows": 0,
        "missing_required_reports": missing,
        "manifest_path": str(manifest_path),
    }


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
