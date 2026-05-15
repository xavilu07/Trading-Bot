from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from trading_signals.application.use_cases.dashboard_reader import build_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(limit: int = 10) -> dict[str, object]:
    return build_dashboard_summary(
        data_path=Path("data"),
        logs_path=Path("logs"),
        runtime_path=Path(".runtime"),
        latest_limit=max(1, min(limit, 50)),
    )
