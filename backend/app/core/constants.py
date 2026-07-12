"""System-wide constants and Enums.

Defines the core node labels, relationship types, and law names to avoid magic strings.
"""

from enum import Enum


class LawName(str, Enum):
    """Supported laws in the MVP scope."""

    GDPR = "GDPR"
    DPDP = "DPDP"
    AI_ACT = "AI_ACT"


class NodeLabel(str, Enum):
    """Neo4j Node Labels representing legal units and structures."""

    LAW = "Law"
    CHAPTER = "Chapter"
    ARTICLE = "Article"
    SECTION = "Section"
    DEFINITION = "Definition"
    CONCEPT = "Concept"
    PENALTY = "Penalty"
    EXCEPTION = "Exception"
    REQUIREMENT = "Requirement"
    COUNTRY = "Country"
    AUTHORITY = "Authority"
    COURT_CASE = "CourtCase"
    GUIDANCE = "Guidance"


class RelationshipType(str, Enum):
    """Neo4j Relationship types representing legal structure and semantic connections."""

    HAS_CHAPTER = "HAS_CHAPTER"
    HAS_ARTICLE = "HAS_ARTICLE"
    HAS_SECTION = "HAS_SECTION"
    DEFINES = "DEFINES"
    REFERENCES = "REFERENCES"
    HAS_EXCEPTION = "HAS_EXCEPTION"
    HAS_REQUIREMENT = "HAS_REQUIREMENT"
    INTERPRETS = "INTERPRETS"
    USES = "USES"
    HAS_CONCEPT = "HAS_CONCEPT"
