from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from trading_signals.interfaces.api.routes.ai import router as ai_router
from trading_signals.interfaces.api.routes.analysis import router as analysis_router
from trading_signals.interfaces.api.routes.dashboard import router as dashboard_router
from trading_signals.interfaces.api.routes.health import router as health_router
from trading_signals.interfaces.api.routes.signals import router as signals_router

app = FastAPI(title="Trading Signals API", version="0.1.0")
app.include_router(health_router)
app.include_router(analysis_router)
app.include_router(signals_router)
app.include_router(dashboard_router)
app.include_router(ai_router)

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/")
def frontend_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
