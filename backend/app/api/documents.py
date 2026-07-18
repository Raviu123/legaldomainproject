"""Documents API endpoint.

Provides endpoints to list ingested laws and retrieve all legal units for a specific law.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.relational import get_db
from app.models.legal_unit import LegalUnit
from app.services.document_service import DocumentService

router = APIRouter()


@router.get("", response_model=List[str])
async def list_ingested_laws(db: AsyncSession = Depends(get_db)) -> List[str]:
    """Returns a list of all laws that have been successfully ingested and normalized."""
    doc_service = DocumentService(db)
    return await doc_service.list_ingested_laws()


@router.get("/{law}", response_model=List[LegalUnit])
async def get_law_documents(law: str, db: AsyncSession = Depends(get_db)) -> List[LegalUnit]:
    """Returns all ingested legal units for a specific law."""
    doc_service = DocumentService(db)
    return await doc_service.get_law_documents(law)
