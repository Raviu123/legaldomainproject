"""Admin API endpoints.

Provides privileged operations that should be protected in production:
  POST /api/v1/admin/ingest   — Trigger ingestion pipeline for a law.
  POST /api/v1/admin/refresh  — Force re-check for law updates.
  GET  /api/v1/admin/status   — Returns pipeline and database health summary.

Security note:
  In production, protect these endpoints with an API key header:
    X-Admin-Key: <ADMIN_API_KEY env var>
  The _require_admin_key dependency handles this.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.constants import LAW_REGISTRY, LawIdentifier, LawStatus
from app.core.logging import logger

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth guard (simple API key — swap for OAuth in production)
# ---------------------------------------------------------------------------


def _require_admin_key(x_admin_key: Optional[str] = Header(default=None)) -> None:
    """Validates the X-Admin-Key header.

    In development (ENVIRONMENT != 'production') the check is bypassed so you
    can call admin endpoints without a key during local development.

    Args:
        x_admin_key: Value of the X-Admin-Key HTTP header.

    Raises:
        HTTPException 401: If key is missing or wrong in production.
    """
    if settings.ENVIRONMENT == "production":
        admin_key = getattr(settings, "ADMIN_API_KEY", None)
        if not admin_key or x_admin_key != admin_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid X-Admin-Key header required.",
            )


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class IngestRequest(BaseModel):
    """Request body for triggering an ingestion job."""

    law: str = Field(
        ...,
        description="Law identifier to ingest (e.g. 'gdpr', 'dpdp'). "
        "Must be registered in LAW_REGISTRY.",
    )
    skip_fetch: bool = Field(
        default=False,
        description="Reuse cached raw file; skip HTTP download.",
    )
    skip_graph: bool = Field(
        default=False,
        description="Skip Neo4j graph loading stages.",
    )
    skip_vector: bool = Field(
        default=False,
        description="Skip Qdrant vector loading stage.",
    )
    force_recreate_vector: bool = Field(
        default=False,
        description="Delete and recreate Qdrant collection before loading.",
    )
    dry_run: bool = Field(
        default=False,
        description="Parse + enrich only; do not write to any database.",
    )


class IngestResponse(BaseModel):
    """Response for an ingest trigger."""

    status: str
    law: str
    message: str


class RegistryEntry(BaseModel):
    """Summary of a law in the registry."""

    identifier: str
    name: str
    full_name: str
    jurisdiction: str
    status: str
    source_url: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/registry", response_model=List[RegistryEntry])
async def list_law_registry(
    _: None = Depends(_require_admin_key),
) -> List[RegistryEntry]:
    """Returns all laws in the registry with their ingestion status."""
    return [
        RegistryEntry(
            identifier=meta["identifier"].value,
            name=meta["name"],
            full_name=meta["full_name"],
            jurisdiction=meta["jurisdiction"].value,
            status=meta["status"].value,
            source_url=meta.get("source_url", ""),
        )
        for meta in LAW_REGISTRY.values()
    ]


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingestion(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(_require_admin_key),
) -> IngestResponse:
    """Triggers the ingestion pipeline for a law as a background task.

    Returns 202 Accepted immediately; the pipeline runs in the background.
    Monitor progress via application logs.
    """
    try:
        law_id = LawIdentifier(request.law)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown law identifier '{request.law}'. "
            f"Valid choices: {[l.value for l in LawIdentifier]}",
        )

    law_meta = LAW_REGISTRY.get(law_id)
    if law_meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Law '{request.law}' is not in the registry.",
        )

    logger.info(f"[AdminAPI] Ingestion triggered for '{law_id.value}' via API.")

    from app.ingestion.run import run_pipeline

    background_tasks.add_task(
        run_pipeline,
        law_id,
        skip_fetch=request.skip_fetch,
        skip_graph=request.skip_graph,
        skip_vector=request.skip_vector,
        force_recreate_vector=request.force_recreate_vector,
        dry_run=request.dry_run,
    )

    return IngestResponse(
        status="accepted",
        law=law_id.value,
        message=(
            f"Ingestion pipeline for '{law_meta['name']}' has been queued. "
            "Monitor progress in application logs."
        ),
    )


@router.post("/check-updates", status_code=status.HTTP_202_ACCEPTED)
async def trigger_update_check(
    background_tasks: BackgroundTasks,
    auto_reingest: bool = False,
    _: None = Depends(_require_admin_key),
) -> Dict[str, Any]:
    """Triggers a background check for source document updates across all ACTIVE laws."""
    from app.jobs.check_updates import check_all_law_updates

    logger.info(f"[AdminAPI] Law update check triggered via API (auto_reingest={auto_reingest}).")
    background_tasks.add_task(check_all_law_updates, auto_reingest)

    return {
        "status": "accepted",
        "message": "Update check queued. Results will be logged.",
        "auto_reingest": auto_reingest,
    }
