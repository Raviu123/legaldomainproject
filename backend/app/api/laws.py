"""Laws catalog API.

Serves law metadata and article contents from the law registry and normalized
data files. Dynamically reflects whatever is registered in LAW_REGISTRY —
no hardcoded law lists in this file.
"""

from typing import List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.relational import get_db, get_legal_units_by_law
from app.core.constants import LAW_REGISTRY, LawIdentifier, LawStatus
from app.models.legal_unit import LegalUnit

router = APIRouter()


class LawMetadata(BaseModel):
    """Schema representing metadata for a law in the catalog."""

    id: str = Field(..., description="Stable identifier (e.g. 'gdpr').")
    name: str = Field(..., description="Short display name (e.g. 'GDPR').")
    full_name: str = Field(..., description="Full legal title.")
    description: str = Field(..., description="Brief scope summary.")
    jurisdiction: str = Field(..., description="Jurisdiction code (e.g. 'EU', 'IN').")
    categories: List[str] = Field(..., description="Thematic categories (e.g. ['DATA_PRIVACY']).")
    status: str = Field(..., description="Ingestion status: 'active' | 'coming_soon' | 'partial'.")
    source_url: str = Field(..., description="Official source URL.")


@router.get("", response_model=List[LawMetadata])
async def list_laws() -> List[LawMetadata]:
    """Returns all supported laws and their ingestion status from the registry.

    This list is driven by LAW_REGISTRY in app/core/constants.py — no
    hardcoded entries in this file.
    """
    return [
        LawMetadata(
            id=meta["identifier"].value,
            name=meta["name"],
            full_name=meta["full_name"],
            description=meta.get("description", ""),
            jurisdiction=meta["jurisdiction"].value,
            categories=[c.value for c in meta.get("categories", [])],
            status=meta["status"].value,
            source_url=meta.get("source_url", ""),
        )
        for meta in LAW_REGISTRY.values()
    ]


@router.get("/{law_id}", response_model=List[LegalUnit])
async def get_law_articles(law_id: str, db: AsyncSession = Depends(get_db)) -> List[LegalUnit]:
    """Returns all parsed and normalized articles/sections for a given law.

    Args:
        law_id: The law identifier string (e.g. 'gdpr', 'dpdp').
        db: Active async database session.

    Raises:
        404: If the law is not in the registry or not yet ingested.
        500: If the database read fails.
    """
    # Validate identifier against registry
    try:
        law_enum = LawIdentifier(law_id.lower())
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Law '{law_id}' is not registered. "
            f"Known laws: {[l.value for l in LawIdentifier]}",
        )

    meta = LAW_REGISTRY.get(law_enum)
    if meta is None or meta["status"] != LawStatus.ACTIVE:
        raise HTTPException(
            status_code=404,
            detail=f"Law '{law_id}' is registered but not yet active "
            f"(status: {meta['status'].value if meta else 'unknown'}). "
            "Run the ingestion pipeline first.",
        )

    try:
        units = await get_legal_units_by_law(db, law_id.upper())
        if not units:
            raise HTTPException(
                status_code=404,
                detail=f"Normalized data for '{law_id}' not found in database. "
                f"Please run the ingestion pipeline for '{law_id}' first.",
            )
        
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
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read normalized law data for '{law_id}': {exc}",
        )
