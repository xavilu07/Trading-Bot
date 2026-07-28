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
from trading_signals.dashboard.queries.read_model import (
    build_freshness_from_read_model,
    build_system_from_read_model,
    read_model_evidence,
)
from trading_signals.interfaces.dashboard_api.settings import DashboardSettings


def create_app(settings: DashboardSettings | None = None) -> FastAPI:
    configured = settings or DashboardSettings.from_env()
    app = FastAPI(
        title="Quantum Bot Dashboard Read-Only API",
        version="1.0.0-foundation",
        description="Isolated foundation API. It exposes no operational controls or performance metrics.",
    )
    app.state.dashboard_settings = configured

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
            read_model=read_model_evidence(configured.resolved_read_model_path(), now=now),
        )

    @app.get("/api/v1/system", response_model=SystemStatus)
    async def system(request: Request) -> SystemStatus:
        return build_system_from_read_model(
            request.app.state.dashboard_settings.resolved_read_model_path()
        )

    @app.get("/api/v1/metadata/freshness", response_model=MetadataFreshness)
    async def metadata_freshness(request: Request) -> MetadataFreshness:
        return build_freshness_from_read_model(
            request.app.state.dashboard_settings.resolved_read_model_path()
        )

    return app


app = create_app()
