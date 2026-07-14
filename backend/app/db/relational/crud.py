"""Database operations (CRUD) for PostgreSQL.
"""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select as sqlmodel_select

from app.db.relational.models import LawDb, LegalUnitDb


async def upsert_law_metadata(session: AsyncSession, law: LawDb) -> LawDb:
    """Upserts metadata for a law (inserts if new, updates existing fields).

    Args:
        session: Active async database session.
        law: LawDb schema instance.

    Returns:
        LawDb: The inserted/updated law instance.
    """
    existing = await session.get(LawDb, law.id)
    if existing:
        existing.name = law.name
        existing.full_name = law.full_name
        existing.description = law.description
        existing.jurisdiction = law.jurisdiction
        existing.status = law.status
        existing.source_url = law.source_url
        existing.categories = law.categories
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return existing
    else:
        session.add(law)
        await session.commit()
        await session.refresh(law)
        return law


async def get_all_laws(session: AsyncSession) -> List[LawDb]:
    """Retrieves all registered laws from the database.
    """
    result = await session.execute(select(LawDb))
    return list(result.scalars().all())


async def get_law_by_id(session: AsyncSession, law_id: str) -> Optional[LawDb]:
    """Gets a single law by its primary key ID.
    """
    return await session.get(LawDb, law_id.lower())


async def bulk_upsert_legal_units(session: AsyncSession, units: List[LegalUnitDb]) -> None:
    """Saves a batch of LegalUnitDb records, updating existing records on primary key conflict.
    """
    for unit in units:
        existing = await session.get(LegalUnitDb, unit.id)
        if existing:
            existing.law = unit.law
            existing.chapter = unit.chapter
            existing.article = unit.article
            existing.section = unit.section
            existing.title = unit.title
            existing.text = unit.text
            existing.source = unit.source
            existing.url = unit.url
            existing.definitions = unit.definitions
            existing.concepts = unit.concepts
            existing.references = unit.references
            session.add(existing)
        else:
            session.add(unit)
    
    await session.commit()


async def get_legal_units_by_law(session: AsyncSession, law_name: str) -> List[LegalUnitDb]:
    """Retrieves all legal units/articles for a specific law.
    """
    stmt = select(LegalUnitDb).where(LegalUnitDb.law == law_name)
    result = await session.execute(stmt)
    return list(result.scalars().all())
