"""Documents API endpoint.

Provides endpoints to list ingested laws and retrieve all legal units for a specific law.
"""

from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.relational import get_db, get_all_laws, get_legal_units_by_law
from app.models.legal_unit import LegalUnit

router = APIRouter()


@router.get("", response_model=List[str])
async def list_ingested_laws(db: AsyncSession = Depends(get_db)) -> List[str]:
    """Returns a list of all laws that have been successfully ingested and normalized."""
    try:
        laws = await get_all_laws(db)
        return sorted([law.id.upper() for law in laws])
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list ingested laws: {str(e)}"
        )


@router.get("/{law}", response_model=List[LegalUnit])
async def get_law_documents(law: str, db: AsyncSession = Depends(get_db)) -> List[LegalUnit]:
    """Returns all ingested legal units for a specific law (e.g., GDPR, DPDP, AI_ACT)."""
    try:
        # DB law name matches uppercase as stored in LegalUnit.law (e.g. GDPR)
        units = await get_legal_units_by_law(db, law.upper())
        if not units:
            raise HTTPException(
                status_code=404,
                detail=f"Ingested data for law '{law}' not found. Please run the ingestion pipeline first."
            )

        # Map to Pydantic schemas
        return [
            LegalUnit(
                id=u.id,
                law=u.law,
                chapter=u.chapter,
                article=u.article,
                section=u.section,
                title=u.title,
                text=u.text,
                source=u.source,
                url=u.url,
                definitions=u.definitions,
                concepts=u.concepts,
                references=u.references,
            )
            for u in units
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve normalized data for '{law}': {str(e)}"
        )
