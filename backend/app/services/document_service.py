from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.repositories.law_repository import LawRepository
from app.repositories.legal_unit_repository import LegalUnitRepository
from app.models.legal_unit import LegalUnit, DefinitionModel

class DocumentService:
    """Service handling law catalog lists and document mappings."""

    def __init__(self, session: AsyncSession, law_repo: LawRepository = None, legal_unit_repo: LegalUnitRepository = None) -> None:
        self.law_repo = law_repo or LawRepository(session)
        self.legal_unit_repo = legal_unit_repo or LegalUnitRepository(session)

    async def list_ingested_laws(self) -> List[str]:
        """Returns a list of all laws that have been successfully ingested and normalized."""
        try:
            laws = await self.law_repo.get_all()
            return sorted([law.id.upper() for law in laws])
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list ingested laws: {str(e)}"
            )

    async def get_law_documents(self, law: str) -> List[LegalUnit]:
        """Returns all ingested legal units for a specific law, mapped to Pydantic schemas."""
        try:
            units = await self.legal_unit_repo.get_by_law(law.upper())
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
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve normalized data for '{law}': {str(e)}"
            )
