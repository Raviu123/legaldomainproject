"""Structure extractor module.

Analyzes normalized legal units to extract legal definitions and cross-references.
Implements Step 3 & 4 of context.md for building graph structure.

Definition extraction is law-aware:
  - GDPR Article 4  : '(1) "personal data" means ...' (numbered clauses, double quotes)
  - DPDP Section 2  : '(a) \u2018personal data\u2019 means ...' (alpha clauses, curly single quotes)
  - Future laws     : Add a new extract_definitions_<law>() function and wire it in
                      enrich_legal_structure() by checking unit.law + unit.article.
"""

import re
from typing import List

from app.core.logging import logger
from app.models.legal_unit import DefinitionModel, LegalUnit


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# All supported quote variants around a defined term.
# The MeitY DPDP gazette PDF uses U+201C/U+201D (“/”) curly double quotes.
# Also covers: standard " ‘ ’ and the replacement char \ufffd (encoding fallback).
_QUOTE_OPEN  = r"[\u201c\u201d\u2018\u2019\ufffd'\"]"
_QUOTE_CLOSE = r"[\u201c\u201d\u2018\u2019\ufffd'\"]"
# Character class for the term itself (everything except quote chars)
_TERM_BODY   = r"[^\u201c\u201d\u2018\u2019\ufffd'\"]+"


# ---------------------------------------------------------------------------
# GDPR — Article 4 definition extractor
# ---------------------------------------------------------------------------

_GDPR_DEF_RE = re.compile(
    rf"^\s*\((\d+)\)\s*{_QUOTE_OPEN}({_TERM_BODY}){_QUOTE_CLOSE}"
    rf"\s+(?:means|shall mean)\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def extract_definitions_from_gdpr_art4(text: str) -> List[DefinitionModel]:
    """Extracts defined terms from GDPR Article 4.

    Pattern: '(1) "personal data" means any information...'

    Args:
        text: Full text of GDPR Article 4.

    Returns:
        List of DefinitionModel objects.
    """
    definitions: List[DefinitionModel] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if m := _GDPR_DEF_RE.match(line):
            term = m.group(2).strip()
            definition = m.group(3).strip()
            definitions.append(DefinitionModel(term=term, definition=definition))

    logger.debug(f"Extracted {len(definitions)} definitions from GDPR Article 4.")
    return definitions


# ---------------------------------------------------------------------------
# DPDP — Section 2 definition extractor
# ---------------------------------------------------------------------------

# Pattern: (a) \u2018Appellate Tribunal\u2019 means ...
#   OR     (za) \u2018specified purpose\u2019 means ...
# The clause letter can be single (a-z) or extended (za, zb, ...)
_DPDP_DEF_RE = re.compile(
    rf"^\s*\(([a-z]{{1,2}})\)\s*"           # clause marker: (a), (za), (zb) …
    rf"{_QUOTE_OPEN}({_TERM_BODY}){_QUOTE_CLOSE}"  # quoted term
    rf"\s+(?:means|shall mean|includes)\s+(.+)$",  # definition verb + text
    re.IGNORECASE | re.DOTALL,
)

# Secondary pattern: clause letter then unquoted CAPITALISED term then "means"
# e.g. "(s) Member means a member of..."
_DPDP_DEF_UNQUOTED_RE = re.compile(
    r"^\s*\(([a-z]{1,2})\)\s+([A-Z][a-zA-Z\s]{2,40}?)\s+(?:means|shall mean|includes)\s+(.+)$",
    re.DOTALL,
)


def extract_definitions_from_dpdp_sec2(text: str) -> List[DefinitionModel]:
    """Extracts defined terms from DPDP Act Section 2.

    DPDP uses curly/smart single quotes around defined terms, and alpha
    clause markers (a)–(zb).

    Patterns handled:
      (a) \u2018Appellate Tribunal\u2019 means ...    (curly quotes)
      (n) \u2018digital personal data\u2019 means ...
      (za) \u2018specified purpose\u2019 means ...     (extended clause letters)

    Multi-line definitions: the definition text often continues on the next
    line(s). We do a greedy merge — accumulate continuation lines until we
    hit the next clause marker.

    Args:
        text: Full text of DPDP Section 2.

    Returns:
        List of DefinitionModel objects.
    """
    definitions: List[DefinitionModel] = []
    lines = text.split("\n")

    current_term: str | None = None
    current_def_lines: List[str] = []

    def flush() -> None:
        nonlocal current_term, current_def_lines
        if current_term and current_def_lines:
            defn_text = " ".join(current_def_lines).strip()
            # Strip trailing semicolons (clause enders) and trailing noise
            defn_text = defn_text.rstrip(";").strip()
            if defn_text:
                definitions.append(DefinitionModel(term=current_term, definition=defn_text))
        current_term = None
        current_def_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Try quoted definition pattern first (most reliable)
        if m := _DPDP_DEF_RE.match(stripped):
            flush()
            current_term = m.group(2).strip()
            current_def_lines = [m.group(3).strip()]
            continue

        # Try unquoted CAPITALISED term pattern
        if m := _DPDP_DEF_UNQUOTED_RE.match(stripped):
            flush()
            current_term = m.group(2).strip()
            current_def_lines = [m.group(3).strip()]
            continue

        # If inside a definition block, check if this is a new clause (a)/(b)/...
        # If so, it's a new definition; otherwise it's a continuation line
        if current_term:
            new_clause = re.match(r"^\s*\([a-z]{1,2}\)\s+", stripped)
            if new_clause:
                # Looks like a new sub-clause that starts a new definition
                # Try again as definition
                if m := _DPDP_DEF_RE.match(stripped):
                    flush()
                    current_term = m.group(2).strip()
                    current_def_lines = [m.group(3).strip()]
                    continue
                # A clause that's NOT a definition — flush current and stop
                flush()
            else:
                # Continuation of current definition text
                current_def_lines.append(stripped)

    flush()

    logger.debug(f"Extracted {len(definitions)} definitions from DPDP Section 2.")
    return definitions


# ---------------------------------------------------------------------------
# Cross-reference extractor (shared across all laws)
# ---------------------------------------------------------------------------

_ART_REF_RE = re.compile(r"\bArticle\s+(\d+)\b", re.IGNORECASE)
_SEC_REF_RE = re.compile(r"\bSection\s+(\d+)\b", re.IGNORECASE)


def extract_cross_references(text: str, law_prefix: str) -> List[str]:
    """Extracts references to other articles/sections in the same law.

    Args:
        text: The text content to search.
        law_prefix: Lowercase law identifier prefix (e.g. 'gdpr', 'dpdp', 'aia').

    Returns:
        Sorted list of referenced unit IDs (e.g. ['gdpr:art6', 'dpdp:sec16']).
    """
    references: set[str] = set()

    for art_num in _ART_REF_RE.findall(text):
        references.add(f"{law_prefix}:art{art_num}")

    for sec_num in _SEC_REF_RE.findall(text):
        references.add(f"{law_prefix}:sec{sec_num}")

    return sorted(references)


# ---------------------------------------------------------------------------
# Map: (law_name, article_identifier) → definition extractor function
# Extend this dict to add definition extraction for new laws.
# ---------------------------------------------------------------------------

_DEFINITION_EXTRACTORS = {
    ("GDPR", "Article 4"):   extract_definitions_from_gdpr_art4,
    ("DPDP", "Section 2"):   extract_definitions_from_dpdp_sec2,
}


# ---------------------------------------------------------------------------
# Main enrichment function
# ---------------------------------------------------------------------------


def enrich_legal_structure(units: List[LegalUnit]) -> List[LegalUnit]:
    """Enriches legal units with definitions and cross-references.

    For each unit:
      1. Extracts cross-references to other articles/sections in the same law.
      2. If the unit is a known definitions section (e.g. GDPR Art 4, DPDP Sec 2),
         runs the appropriate extractor.

    Args:
        units: List of normalized legal units (post-parse, pre-graph-load).

    Returns:
        The same list with .references and .definitions populated.
    """
    law_prefix_overrides = {
        "ai_act": "aia",
    }

    enriched: List[LegalUnit] = []
    definition_totals: dict[str, int] = {}

    for unit in units:
        law_lower = unit.law.lower()
        law_prefix = law_prefix_overrides.get(law_lower, law_lower)

        # 1. Cross-references
        refs = extract_cross_references(unit.text, law_prefix)
        # Remove self-references
        unit.references = [r for r in refs if r != unit.id]

        # 2. Definitions — dispatch by (law, article) key
        article_key = (unit.law.upper(), (unit.article or "").strip())
        extractor = _DEFINITION_EXTRACTORS.get(article_key)
        if extractor:
            defs = extractor(unit.text)
            unit.definitions = defs
            definition_totals[unit.id] = len(defs)
            logger.info(
                f"[StructureExtractor] {unit.id}: extracted {len(defs)} definitions."
            )

        enriched.append(unit)

    if definition_totals:
        logger.info(f"[StructureExtractor] Definition extraction summary: {definition_totals}")

    return enriched
