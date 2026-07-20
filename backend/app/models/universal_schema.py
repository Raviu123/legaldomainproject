"""Universal Pydantic schema for LLM-based legal document parsing."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ExtractedLegalUnit(BaseModel):
    """A single legal unit extracted from a statutory text chunk."""

    chapter: str = Field(
        default="General Provisions",
        description="Chapter, Part, or Title header (e.g., 'Chapter I — Preliminary').",
    )
    article_or_section: str = Field(
        ...,
        description="Article or Section label and number (e.g., 'Article 6', 'Section 12').",
    )
    title: str = Field(
        default="",
        description="Title or subject header of the section/article (e.g., 'Lawfulness of Processing').",
    )
    body_text: str = Field(
        ...,
        description="Complete text content of this section/article including sub-clauses and provisos.",
    )
    defined_terms: List[str] = Field(
        default_factory=list,
        description="List of legal terms defined in this specific section, if any.",
    )
    cross_references: List[str] = Field(
        default_factory=list,
        description="Raw cross-reference citations mentioned in this section (e.g., ['Article 4', 'Section 7']).",
    )


class ExtractedDocumentPayload(BaseModel):
    """Payload container for batch LLM extraction."""

    units: List[ExtractedLegalUnit] = Field(
        default_factory=list,
        description="List of extracted legal units.",
    )
