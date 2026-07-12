"""Laws API router.

Serves lists of laws and their articles/sections directly from the ingested data directory.
"""

import json
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.core.config import settings
from app.models.legal_unit import LegalUnit

router = APIRouter()


class LawMetadata(BaseModel):
    """Schema representing metadata for a law."""

    id: str = Field(..., description="Unique identifier for the law (e.g. 'gdpr').")
    name: str = Field(..., description="Short name of the law.")
    fullName: str = Field(..., description="Full legal title of the law.")
    description: str = Field(..., description="Brief summary of the law's scope.")
    region: str = Field(..., description="Geographical jurisdiction.")
    status: str = Field(..., description="Ingestion status ('active' or 'coming_soon').")


@router.get("", response_model=List[LawMetadata])
async def list_laws() -> List[LawMetadata]:
    """Returns a list of all supported laws and their ingestion status."""
    return [
        LawMetadata(
            id="gdpr",
            name="GDPR",
            fullName="General Data Protection Regulation (EU)",
            description=(
                "Regulation on the protection of natural persons with regard to the processing "
                "of personal data and on the free movement of such data."
            ),
            region="European Union",
            status="active",
        ),
        LawMetadata(
            id="dpdp",
            name="DPDP Act",
            fullName="Digital Personal Data Protection Act, 2023 (India)",
            description=(
                "An Act to provide for the processing of digital personal data in a manner that "
                "recognizes both the right of individuals to protect their personal data and the "
                "need to process such personal data for lawful purposes."
            ),
            region="India",
            status="coming_soon",
        ),
        LawMetadata(
            id="ai_act",
            name="AI Act",
            fullName="Artificial Intelligence Act (EU)",
            description="A harmonized regulatory and legal framework for artificial intelligence across the European Union.",
            region="European Union",
            status="coming_soon",
        ),
    ]


@router.get("/{law_id}", response_model=List[LegalUnit])
async def get_law_articles(law_id: str) -> List[LegalUnit]:
    """Retrieves all parsed and normalized articles/sections for a given law."""
    if law_id != "gdpr":
        raise HTTPException(
            status_code=404,
            detail=f"Law '{law_id}' not found or not yet active in ingestion.",
        )

    file_path = settings.normalized_data_dir / "gdpr.json"

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Normalized data file for law '{law_id}' was not found at {file_path}.",
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read or parse normalized law data: {str(e)}",
        )
