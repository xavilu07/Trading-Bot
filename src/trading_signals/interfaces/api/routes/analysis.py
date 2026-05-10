from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from trading_signals.app.container import build_container
from trading_signals.application.use_cases.run_market_scan import run_market_scan

router = APIRouter(prefix="/v1/scans", tags=["analysis"])


class RunScanRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    dry_run: bool = False


@router.post("/run")
def run_scan(payload: RunScanRequest) -> dict[str, object]:
    container = build_container()
    result = run_market_scan(
        settings=container["settings"],
        market_data=container["market_data"],
        scan_repo=container["scan_repo"],
        signal_repo=container["signal_repo"],
        notifier=container["notifier"],
        diagnostics_store=container["diagnostics_store"],
        metrics=container["metrics"],
        paper_trading_store=container["paper_trading_store"],
        symbols=payload.symbols or None,
        dry_run=payload.dry_run,
    )
    return {
        "scan_run_id": result["scan_run"]["id"],
        "status": result["scan_run"]["status"],
        "symbols_total": result["scan_run"]["symbols_total"],
        "results_count": len(result["results"]),
    }
