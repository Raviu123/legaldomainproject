"""Admin API endpoints.

Provides privileged operations that should be protected in production.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.constants import LawIdentifier
from app.services.admin_service import AdminService, RegistryEntry, IngestResponse

router = APIRouter()
admin_service = AdminService()


# ---------------------------------------------------------------------------
# Auth guard (simple API key — swap for OAuth in production)
# ---------------------------------------------------------------------------


def _require_admin_key(x_admin_key: Optional[str] = Header(default=None)) -> None:
    """Validates the X-Admin-Key header."""
    if settings.ENVIRONMENT == "production":
        admin_key = getattr(settings, "ADMIN_API_KEY", None)
        if not admin_key or x_admin_key != admin_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid X-Admin-Key header required.",
            )


# ---------------------------------------------------------------------------
# Request / Response models (specific to API schema parameters validation)
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/registry", response_model=List[RegistryEntry])
async def list_law_registry(
    _: None = Depends(_require_admin_key),
) -> List[RegistryEntry]:
    """Returns all laws in the registry with their ingestion status."""
    return admin_service.list_law_registry()


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingestion(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(_require_admin_key),
) -> IngestResponse:
    """Triggers the ingestion pipeline for a law as a background task."""
    return admin_service.trigger_ingestion(
        law_name=request.law,
        skip_fetch=request.skip_fetch,
        skip_graph=request.skip_graph,
        skip_vector=request.skip_vector,
        force_recreate_vector=request.force_recreate_vector,
        dry_run=request.dry_run,
        background_tasks=background_tasks,
    )


@router.post("/check-updates", status_code=status.HTTP_202_ACCEPTED)
async def trigger_update_check(
    background_tasks: BackgroundTasks,
    auto_reingest: bool = False,
    _: None = Depends(_require_admin_key),
) -> Dict[str, Any]:
    """Triggers a background check for source document updates across all ACTIVE laws."""
    return admin_service.trigger_update_check(
        auto_reingest=auto_reingest,
        background_tasks=background_tasks,
    )
