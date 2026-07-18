from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import BackgroundTasks, HTTPException, status

from app.core.config import settings
from app.core.constants import LAW_REGISTRY, LawIdentifier, LawStatus
from app.core.logging import logger
from app.ingestion.run import run_pipeline
from app.jobs.check_updates import check_all_law_updates

class RegistryEntry(BaseModel):
    """Summary of a law in the registry."""

    identifier: str
    name: str
    full_name: str
    jurisdiction: str
    status: str
    source_url: str


class IngestResponse(BaseModel):
    """Response for an ingest trigger."""

    status: str
    law: str
    message: str


class AdminService:
    """Service to handle administrative tasks such as ingestion and updates checks."""

    def __init__(self) -> None:
        pass

    def list_law_registry(self) -> List[RegistryEntry]:
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

    def trigger_ingestion(self, law_name: str, skip_fetch: bool, skip_graph: bool, skip_vector: bool, force_recreate_vector: bool, dry_run: bool, background_tasks: BackgroundTasks) -> IngestResponse:
        """Triggers the ingestion pipeline for a law as a background task."""
        try:
            law_id = LawIdentifier(law_name)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown law identifier '{law_name}'. "
                f"Valid choices: {[l.value for l in LawIdentifier]}",
            )

        law_meta = LAW_REGISTRY.get(law_id)
        if law_meta is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Law '{law_name}' is not in the registry.",
            )

        logger.info(f"[AdminService] Ingestion triggered for '{law_id.value}' via Service.")

        background_tasks.add_task(
            run_pipeline,
            law_id,
            skip_fetch=skip_fetch,
            skip_graph=skip_graph,
            skip_vector=skip_vector,
            force_recreate_vector=force_recreate_vector,
            dry_run=dry_run,
        )

        return IngestResponse(
            status="accepted",
            law=law_id.value,
            message=(
                f"Ingestion pipeline for '{law_meta['name']}' has been queued. "
                "Monitor progress in application logs."
            ),
        )

    def trigger_update_check(self, auto_reingest: bool, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        """Triggers a background check for source document updates across all ACTIVE laws."""
        logger.info(f"[AdminService] Law update check triggered via Service (auto_reingest={auto_reingest}).")
        background_tasks.add_task(check_all_law_updates, auto_reingest)

        return {
            "status": "accepted",
            "message": "Update check queued. Results will be logged.",
            "auto_reingest": auto_reingest,
        }
