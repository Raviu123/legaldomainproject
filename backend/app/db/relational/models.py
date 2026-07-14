"""SQLModel database tables for PostgreSQL.
"""

from typing import Any, Dict, List, Optional
from sqlmodel import Column, Field, JSON, SQLModel


class LawDb(SQLModel, table=True):
    """Database model for storing law metadata."""

    __tablename__ = "laws"

    id: str = Field(primary_key=True, description="Stable identifier (e.g. 'gdpr').")
    name: str = Field(description="Short display name (e.g. 'GDPR').")
    full_name: str = Field(description="Full legal title.")
    description: Optional[str] = Field(default=None, description="Brief scope summary.")
    jurisdiction: str = Field(description="Jurisdiction code (e.g. 'EU', 'IN').")
    status: str = Field(description="Ingestion status: 'active' | 'coming_soon'.")
    source_url: str = Field(description="Official source URL.")
    categories: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Thematic categories of the law.",
    )


class LegalUnitDb(SQLModel, table=True):
    """Database model for storing normalized legal units."""

    __tablename__ = "legal_units"

    id: str = Field(primary_key=True, description="Unique identifier (e.g. 'gdpr:art6').")
    law: str = Field(index=True, description="The name of the law (e.g. 'GDPR').")
    chapter: str = Field(description="The chapter containing this unit (e.g. 'Chapter II').")
    article: Optional[str] = Field(default=None, description="The article identifier.")
    section: Optional[str] = Field(default=None, description="The section identifier.")
    title: Optional[str] = Field(default=None, description="The title or header of the unit.")
    text: str = Field(description="The actual text content of the unit.")
    source: str = Field(description="The name of the source provider.")
    url: str = Field(description="The source URL for validation.")

    # Nested structures stored as JSON columns
    definitions: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Definitions defined within this unit.",
    )
    concepts: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Semantic concepts extracted from this unit.",
    )
    references: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="List of unit IDs that this unit references.",
    )
