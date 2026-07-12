"""Structure extractor module.

Analyzes normalized legal units to extract legal definitions and cross-references.
Implements Step 3 & 4 of context.md for building graph structure.
"""

import re
from typing import List

from app.core.logging import logger
from app.models.legal_unit import DefinitionModel, LegalUnit


def extract_definitions_from_gdpr_art4(text: str) -> List[DefinitionModel]:
    """Extracts defined terms from the text of GDPR Article 4.

    Each paragraph in GDPR Article 4 generally has the form:
    '(1) ‘personal data’ means any information...'

    Args:
        text: The full text of GDPR Article 4.

    Returns:
        List[DefinitionModel]: List of extracted definitions.
    """
    definitions: List[DefinitionModel] = []

    # Split text by lines or paragraph breaks
    lines = text.split("\n")

    # Regex to match: (1) 'personal data' means ...
    # Support smart quotes (‘‘, ’’), standard single quotes, and double quotes.
    def_regex = re.compile(
        r"^\s*\((\d+)\)\s*[‘'\"“]([^’'\"”]+)[’'\"”]\s+(?:means|shall mean)\s+(.+)$",
        re.IGNORECASE | re.DOTALL,
    )

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = def_regex.match(line)
        if match:
            term = match.group(2).strip()
            def_text = match.group(3).strip()
            definitions.append(DefinitionModel(term=term, definition=def_text))

    logger.debug(f"Extracted {len(definitions)} definitions from GDPR Article 4")
    return definitions


def extract_cross_references(text: str, law_prefix: str) -> List[str]:
    """Extracts references to other articles in the same law.

    Looks for patterns like 'Article 6', 'Article 9(2)', etc.

    Args:
        text: The text content to search.
        law_prefix: Prefix of the law (e.g. 'gdpr' for GDPR, 'dpdp' for DPDP).

    Returns:
        List[str]: List of referenced unit IDs (e.g. ['gdpr:art6', 'gdpr:art9']).
    """
    # Matches 'Article 6', 'Article 32', etc.
    art_ref_regex = re.compile(r"\bArticle\s+(\d+)\b", re.IGNORECASE)

    # Matches 'Section 16', 'Section 5', etc. (for Indian laws like DPDP)
    sec_ref_regex = re.compile(r"\bSection\s+(\d+)\b", re.IGNORECASE)

    references = set()

    # Extract Article references
    for art_num in art_ref_regex.findall(text):
        ref_id = f"{law_prefix}:art{art_num}"
        references.add(ref_id)

    # Extract Section references
    for sec_num in sec_ref_regex.findall(text):
        ref_id = f"{law_prefix}:sec{sec_num}"
        references.add(ref_id)

    return sorted(list(references))


def enrich_legal_structure(units: List[LegalUnit]) -> List[LegalUnit]:
    """Enriches legal units with definitions and cross-references.

    Args:
        units: List of normalized legal units.

    Returns:
        List[LegalUnit]: The enriched legal units.
    """
    enriched_units = []

    for unit in units:
        # Determine prefix for references (e.g. 'gdpr', 'dpdp')
        law_prefix = unit.law.lower()
        if law_prefix == "ai_act":
            law_prefix = "aia"

        # Extract cross-references
        refs = extract_cross_references(unit.text, law_prefix)
        # Avoid self-referencing
        if unit.id in refs:
            refs.remove(unit.id)
        unit.references = refs

        # GDPR-specific Article 4 definition extraction
        if unit.law == "GDPR" and unit.article == "Article 4":
            unit.definitions = extract_definitions_from_gdpr_art4(unit.text)

        enriched_units.append(unit)

    return enriched_units
