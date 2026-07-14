"""PostgreSQL connection and session management.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import SQLModel

from app.core.config import settings
from app.core.logging import logger

# Create the async database engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

# Async session maker
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Creates all database tables defined in SQLModel metadata if they do not exist.
    """
    logger.info("Initializing relational database tables...")
    try:
        async with engine.begin() as conn:
            # We import models here to ensure they are registered with SQLModel.metadata
            from app.db.relational.models import LawDb, LegalUnitDb
            await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("Relational database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize relational database tables: {e}")
        raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency generator for database sessions.
    
    Yields:
        AsyncSession: An active async database session.
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
