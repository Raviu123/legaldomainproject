from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.relational.models import LegalUnitDb
from app.db.relational.crud import (
    bulk_upsert_legal_units,
    get_legal_units_by_law,
)

class LegalUnitRepository:
    """Repository handling all database operations for LegalUnits."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_upsert(self, units: List[LegalUnitDb]) -> None:
        """Saves a batch of LegalUnitDb records, updating existing records on conflict."""
        await bulk_upsert_legal_units(self.session, units)

    async def get_by_law(self, law_name: str) -> List[LegalUnitDb]:
        """Retrieves all legal units/articles for a specific law."""
        return await get_legal_units_by_law(self.session, law_name)
