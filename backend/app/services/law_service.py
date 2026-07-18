from typing import List
from pydantic import BaseModel, Field
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.law_repository import LawRepository
from app.repositories.legal_unit_repository import LegalUnitRepository
from app.core.constants import LAW_REGISTRY, LawIdentifier, LawStatus
from app.models.legal_unit import LegalUnit, DefinitionModel

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


class LawService:
    """Service to handle operations on the law catalog and article retrieval."""

    def __init__(self, session: AsyncSession, law_repo: LawRepository = None, legal_unit_repo: LegalUnitRepository = None) -> None:
        self.law_repo = law_repo or LawRepository(session)
        self.legal_unit_repo = legal_unit_repo or LegalUnitRepository(session)

    def list_laws(self) -> List[LawMetadata]:
        """Returns all supported laws and their ingestion status from the registry."""
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

    async def get_law_articles(self, law_id: str) -> List[LegalUnit]:
        """Returns all parsed and normalized articles/sections for a given law."""
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
            units = await self.legal_unit_repo.get_by_law(law_id.upper())
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
                    definitions=[
                        DefinitionModel(term=d.get("term", ""), definition=d.get("definition", ""))
                        if isinstance(d, dict) else d
                        for d in u.definitions
                    ],
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
