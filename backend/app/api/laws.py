"""Laws catalog API.

Serves law metadata and article contents from the law registry and normalized data files.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.relational import get_db
from app.models.legal_unit import LegalUnit
from app.services.law_service import LawService, LawMetadata

router = APIRouter()


@router.get("", response_model=List[LawMetadata])
async def list_laws() -> List[LawMetadata]:
    """Returns all supported laws and their ingestion status from the registry."""
    # Instantiated without db since catalog listing only reads static registry
    law_service = LawService(session=None)
    return law_service.list_laws()


@router.get("/{law_id}", response_model=List[LegalUnit])
async def get_law_articles(law_id: str, db: AsyncSession = Depends(get_db)) -> List[LegalUnit]:
    """Returns all parsed and normalized articles/sections for a given law."""
    law_service = LawService(db)
    return await law_service.get_law_articles(law_id)
