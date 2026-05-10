from __future__ import annotations

from fastapi import APIRouter, HTTPException

from trading_signals.app.container import build_container

router = APIRouter(prefix="/v1/signals", tags=["signals"])


@router.get("/latest")
def latest(limit: int = 20) -> list[dict[str, object]]:
    container = build_container()
    return container["signal_repo"].list_latest_signals(limit=limit)


@router.get("/{signal_id}")
def get_signal(signal_id: str) -> dict[str, object]:
    container = build_container()
    signal = container["signal_repo"].get_signal(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal

