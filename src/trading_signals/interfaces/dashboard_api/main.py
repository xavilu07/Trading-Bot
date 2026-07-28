from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, Request

from trading_signals.dashboard.contracts import (
    ApiHealth,
    DataClassification,
    EvidenceReference,
    Freshness,
    FreshnessStatus,
    MetadataFreshness,
    OperationalStatus,
    StatusEvidence,
    SystemStatus,
)
from trading_signals.dashboard.ingestion import SourceCatalog
from trading_signals.dashboard.queries import build_freshness, build_system_status
from trading_signals.interfaces.dashboard_api.settings import DashboardSettings


def create_app(settings: DashboardSettings | None = None) -> FastAPI:
    configured = settings or DashboardSettings.from_env()
    catalog = SourceCatalog.load_default(configured.source_variables())
    app = FastAPI(
        title="Quantum Bot Dashboard Read-Only API",
        version="1.0.0-foundation",
        description="Isolated foundation API. It exposes no operational controls or performance metrics.",
    )
    app.state.dashboard_settings = configured
    app.state.source_catalog = catalog

    @app.get("/api/v1/health", response_model=ApiHealth)
    async def health() -> ApiHealth:
        now = datetime.now(timezone.utc)
        return ApiHealth(
            generated_at=now,
            api=StatusEvidence(
                status=OperationalStatus.HEALTHY,
                reason="Read-only dashboard API process is responding.",
                observed_at=now,
                source="dashboard_api",
                freshness=Freshness(
                    status=FreshnessStatus.FRESH,
                    age_seconds=0,
                    expected_freshness_seconds=60,
                    observed_event_at=now,
                ),
                evidence_reference=EvidenceReference(
                    source_id="dashboard_api",
                    reference="source:dashboard_api#in-process",
                ),
                classification=DataClassification.REAL,
            ),
        )

    @app.get("/api/v1/system", response_model=SystemStatus)
    async def system(request: Request) -> SystemStatus:
        return build_system_status(request.app.state.source_catalog)

    @app.get("/api/v1/metadata/freshness", response_model=MetadataFreshness)
    async def metadata_freshness(request: Request) -> MetadataFreshness:
        return build_freshness(request.app.state.source_catalog)

    return app


app = create_app()
