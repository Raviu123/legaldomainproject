"""Relational database module package.
"""

from app.db.relational.connection import get_db, init_db, engine
from app.db.relational.models import LawDb, LegalUnitDb
from app.db.relational.crud import (
    upsert_law_metadata,
    get_all_laws,
    get_law_by_id,
    bulk_upsert_legal_units,
    get_legal_units_by_law,
)

__all__ = [
    "engine",
    "get_db",
    "init_db",
    "LawDb",
    "LegalUnitDb",
    "upsert_law_metadata",
    "get_all_laws",
    "get_law_by_id",
    "bulk_upsert_legal_units",
    "get_legal_units_by_law",
]
