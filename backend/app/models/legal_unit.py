"""Pydantic model for LegalUnit.

Every legal unit (article, section, definition, etc.) ingested must conform to this schema.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class DefinitionModel(BaseModel):
    """Sub-schema representing a defined term and its definition."""

    term: str = Field(..., description="The word or term being defined.")
    definition: str = Field(..., description="The definition text of the term.")


class LegalUnit(BaseModel):
    """A standard representation of a single unit of law (usually an Article or Section)."""

    id: str = Field(
        ...,
        description=(
            "Unique identifier for this unit (e.g. 'gdpr:art6', 'dpdp:sec16'). "
            "Used as the join key."
        ),
    )
    law: str = Field(..., description="The name of the law (e.g. 'GDPR', 'DPDP').")
    chapter: str = Field(..., description="The chapter containing this unit (e.g. 'Chapter II').")
    article: Optional[str] = Field(
        None, description="The article identifier (e.g. 'Article 6', 'Section 16')."
    )
    section: Optional[str] = Field(
        None, description="The section identifier or sub-clause number if applicable."
    )
    title: Optional[str] = Field(
        None, description="The title or header of the unit (e.g. 'Lawfulness of processing')."
    )
    text: str = Field(..., description="The actual text content of the legal unit.")
    source: str = Field(..., description="The name of the source provider (e.g. 'eur-lex').")
    url: str = Field(..., description="The source URL for validation and external citation.")

    # Optional metadata populated by structure or entity extraction stages
    definitions: List[DefinitionModel] = Field(
        default_factory=list, description="Definitions defined within this legal unit."
    )
    concepts: List[str] = Field(
        default_factory=list, description="Semantic concepts extracted from this unit."
    )
    references: List[str] = Field(
        default_factory=list,
        description=(
            "List of unit IDs that this unit references or depends on (e.g. ['gdpr:art4'])."
        ),
    )
