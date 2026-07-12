"""Unit tests for the structure extractor.
"""

from app.extraction.structure_extractor import (
    extract_cross_references,
    extract_definitions_from_gdpr_art4,
    enrich_legal_structure,
)
from app.models.legal_unit import LegalUnit


def test_extract_definitions_from_gdpr_art4() -> None:
    """Tests extracting terms and definitions from Article 4 text."""
    sample_text = (
        "For the purposes of this Regulation:\n"
        "(1) ‘personal data’ means any information relating to an identified or identifiable natural person;\n"
        "(2) ‘processing’ means any operation or set of operations which is performed on personal data;\n"
    )
    
    definitions = extract_definitions_from_gdpr_art4(sample_text)
    
    assert len(definitions) == 2
    assert definitions[0].term == "personal data"
    assert definitions[0].definition == "any information relating to an identified or identifiable natural person;"
    assert definitions[1].term == "processing"
    assert definitions[1].definition == "any operation or set of operations which is performed on personal data;"


def test_extract_cross_references() -> None:
    """Tests extracting article and section cross-references."""
    text_with_refs = (
        "Processing shall be lawful only if and to the extent that at least one of the "
        "conditions listed in Article 6 applies. As defined in Section 16 of other act."
    )
    
    refs = extract_cross_references(text_with_refs, "gdpr")
    
    assert refs == ["gdpr:art6", "gdpr:sec16"]


def test_enrich_legal_structure() -> None:
    """Tests the full legal structure enrichment process on a list of LegalUnits."""
    unit_art4 = LegalUnit(
        id="gdpr:art4",
        law="GDPR",
        chapter="Chapter I",
        article="Article 4",
        title="Definitions",
        text="(1) ‘personal data’ means any info.\n(2) ‘processing’ means any operation.",
        source="eur-lex",
        url="https://eur-lex.europa.eu/gdpr",
    )
    
    unit_art6 = LegalUnit(
        id="gdpr:art6",
        law="GDPR",
        chapter="Chapter II",
        article="Article 6",
        title="Lawfulness of processing",
        text="Processing is lawful if conditions in Article 4 are met.",
        source="eur-lex",
        url="https://eur-lex.europa.eu/gdpr",
    )
    
    enriched = enrich_legal_structure([unit_art4, unit_art6])
    
    assert len(enriched) == 2
    
    # Art 4 should have definitions
    assert len(enriched[0].definitions) == 2
    assert enriched[0].definitions[0].term == "personal data"
    
    # Art 6 should have reference to Art 4, and not self-reference itself
    assert enriched[1].references == ["gdpr:art4"]
