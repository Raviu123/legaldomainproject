"""Documents API endpoint.

Provides endpoints to list ingested laws and retrieve all legal units for a specific law.
"""

import json
from typing import List
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.legal_unit import LegalUnit

router = APIRouter()


@router.get("", response_model=List[str])
async def list_ingested_laws() -> List[str]:
    """Returns a list of all laws that have been successfully ingested and normalized."""
    try:
        normalized_dir = settings.normalized_data_dir
        if not normalized_dir.exists():
            return []

        laws = []
        for file in normalized_dir.glob("*.json"):
            # Exclude metadata or helper files if any
            if file.name.startswith("."):
                continue
            laws.append(file.stem.upper())
        return sorted(laws)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list ingested laws: {str(e)}"
        )


@router.get("/{law}", response_model=List[LegalUnit])
async def get_law_documents(law: str) -> List[LegalUnit]:
    """Returns all ingested legal units for a specific law (e.g., GDPR, DPDP, AI_ACT)."""
    law_lower = law.lower()
    file_name = f"{law_lower}.json"
    file_path = settings.normalized_data_dir / file_name

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Ingested data for law '{law}' not found. Please run the ingestion pipeline first."
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Parse and return the legal units
        return [LegalUnit(**item) for item in data]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read or parse normalized data for '{law}': {str(e)}"
        )
