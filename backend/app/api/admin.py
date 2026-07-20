"""Admin / Ingestion API endpoints.

Provides public ingestion operations for law processing.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.constants import LawIdentifier
from app.services.admin_service import AdminService, RegistryEntry, IngestResponse

router = APIRouter()


def get_admin_service() -> AdminService:
    """Dependency provider for AdminService."""
    return AdminService()


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
    admin_service: AdminService = Depends(get_admin_service),
) -> List[RegistryEntry]:
    """Returns all laws in the registry with their ingestion status."""
    return admin_service.list_law_registry()


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingestion(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    admin_service: AdminService = Depends(get_admin_service),
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


@router.post("/ingest-file", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingestion_from_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    law: str = Form(...),
    skip_graph: bool = Form(False),
    skip_vector: bool = Form(False),
    force_recreate_vector: bool = Form(False),
    dry_run: bool = Form(False),
    admin_service: AdminService = Depends(get_admin_service),
) -> IngestResponse:
    """Triggers the ingestion pipeline for a law using a directly uploaded PDF / raw document file."""
    return await admin_service.trigger_ingestion_file(
        file=file,
        law_name=law,
        skip_graph=skip_graph,
        skip_vector=skip_vector,
        force_recreate_vector=force_recreate_vector,
        dry_run=dry_run,
        background_tasks=background_tasks,
    )


@router.post("/check-updates")
async def trigger_check_updates(
    auto_reingest: bool = False,
    background_tasks: BackgroundTasks = None,
    admin_service: AdminService = Depends(get_admin_service),
) -> Dict[str, Any]:
    """Triggers a background check for source document updates across all registered laws."""
    return admin_service.trigger_update_check(
        auto_reingest=auto_reingest,
        background_tasks=background_tasks,
    )


@router.delete("/laws/{law_id}")
async def delete_law(
    law_id: str,
    admin_service: AdminService = Depends(get_admin_service),
) -> Dict[str, Any]:
    """Completely deletes a law from Neo4j, Qdrant, PostgreSQL, disk caches, and LAW_REGISTRY."""
    return await admin_service.delete_law_complete(law_id)
