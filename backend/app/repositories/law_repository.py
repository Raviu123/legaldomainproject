from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.relational.models import LawDb
from app.db.relational.crud import (
    upsert_law_metadata,
    get_all_laws,
    get_law_by_id,
)

class LawRepository:
    """Repository handling all database operations for Law metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, law: LawDb) -> LawDb:
        """Upserts metadata for a law (inserts if new, updates existing fields)."""
        return await upsert_law_metadata(self.session, law)

    async def get_all(self) -> List[LawDb]:
        """Retrieves all registered laws from the database."""
        return await get_all_laws(self.session)

    async def get_by_id(self, law_id: str) -> Optional[LawDb]:
        """Gets a single law by its primary key ID."""
        return await get_law_by_id(self.session, law_id)
