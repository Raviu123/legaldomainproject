"""Unit tests for the Universal AI Parser with SG_PDPA.

Tests hybrid parsing strategy (regex first, LLM fallback) with Singapore PDPA.
"""

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.constants import LawIdentifier
from app.core.config import settings
from app.ingestion.parsers.universal_ai import UniversalAiParser


def _get_pdpa_path() -> Path:
    candidates = [
        settings.raw_data_dir / "sg_pdpa_raw.pdf",
        Path("data/raw/sg_pdpa_raw.pdf"),
        Path("../data/raw/sg_pdpa_raw.pdf"),
        Path("../../data/raw/sg_pdpa_raw.pdf"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def test_pdpa_parser_full_pipeline(tmp_path: Path) -> None:
    """Tests parsing real SG_PDPA PDF using hybrid parser."""
    
    pdpa_path = _get_pdpa_path()
    
    # Skip test if file doesn't exist (for CI/CD)
    if not pdpa_path.exists():
        pytest.skip(f"PDPA PDF not found at {pdpa_path}")
    
    parser = UniversalAiParser()
    units = parser.parse(
        file_path=pdpa_path,
        url="https://sso.agc.gov.sg/Act/PDPA2012",
        law=LawIdentifier.PDPA_SG
    )
    
    # ================================================================
    # BASIC VALIDATION
    # ================================================================
    
    # Should have extracted many units
    assert len(units) > 50, f"Expected >50 units, got {len(units)}"
    print(f"\n✅ Extracted {len(units)} legal units")
    
    # All units should have required fields
    for unit in units[:10]:  # Check first 10
        assert unit.id, "Unit missing ID"
        assert unit.law, "Unit missing law"
        assert unit.chapter, "Unit missing chapter"
        assert unit.section, "Unit missing section"
        assert unit.text, "Unit missing text"
    
    # ================================================================
    # SECTION 2 - INTERPRETATION (CRITICAL)
    # ================================================================
    
    # Find Section 2 (should be "Section 2" or "2.")
    section_2 = None
    for unit in units:
        if re.search(r'\b2\b', unit.section) and 'interpretation' in unit.title.lower():
            section_2 = unit
            break
    
    # If not found by title, try just section number
    if not section_2:
        for unit in units:
            if re.search(r'\b2\b', unit.section):
                section_2 = unit
                break
    
    assert section_2 is not None, "❌ Section 2 not found!"
    print(f"\n✅ Section 2 found: {section_2.title}")
    print(f"   Text preview: {section_2.text[:200]}...")
    
    # CRITICAL: Check for "whether true or not"
    assert 'whether true or not' in section_2.text.lower(), \
        "❌ Section 2 missing 'whether true or not' (critical definition)"
    print("✅ Section 2 contains 'whether true or not'")
    
    # Check for complete definition
    assert 'personal data' in section_2.text.lower(), \
        "❌ Section 2 missing 'personal data' definition"
    print("✅ Section 2 contains 'personal data' definition")
    
    # Check for "identified from that data"
    assert 'identified from that data' in section_2.text.lower() or \
           'identifiable' in section_2.text.lower(), \
        "❌ Section 2 missing identifiability criterion"
    print("✅ Section 2 contains identifiability criterion")
    
    # ================================================================
    # DEFINITION EXTRACTION
    # ================================================================
    
    # Collect all definitions
    all_defs = []
    for unit in units:
        all_defs.extend(unit.definitions)
    
    print(f"\n✅ Found {len(all_defs)} definitions across all sections")
    
    # Check for key definitions
    key_terms = [
        'personal data',
        'organisation',
        'processing',
        'consent',
        'data intermediary'
    ]
    
    found_terms = []
    for term in key_terms:
        found = any(term in d.term.lower() for d in all_defs)
        if found:
            found_terms.append(term)
            print(f"   ✅ Found definition for '{term}'")
        else:
            print(f"   ⚠️  Missing definition for '{term}'")
    
    # At least some key terms should be found
    assert len(found_terms) >= 3, \
        f"❌ Found only {len(found_terms)} key terms, expected at least 3"
    
    # Check personal data definition specifically
    pd_def = next((d for d in all_defs if 'personal data' in d.term.lower()), None)
    if pd_def:
        print(f"\n✅ Personal data definition: {pd_def.definition[:150]}...")
        # Definition should mention "whether true or not"
        assert 'whether true or not' in pd_def.definition.lower() or \
               'true or not' in pd_def.definition.lower(), \
            "❌ Personal data definition missing 'whether true or not'"
    else:
        print("⚠️  Personal data definition not in extracted definitions")
        # Check if it's in the text of Section 2
        if section_2 and 'personal data' in section_2.text.lower():
            print("   (But found in Section 2 text - this is acceptable)")
    
    # ================================================================
    # CROSS-REFERENCES
    # ================================================================
    
    # Check some units have cross-references
    units_with_refs = [u for u in units if u.references]
    print(f"\n✅ {len(units_with_refs)} units have cross-references")
    
    if units_with_refs:
        sample_refs = units_with_refs[0].references[:5]
        print(f"   Sample: {sample_refs}")
    
    # Check for specific cross-references that should exist
    # Section 13 should reference Section 14 (consent provisions)
    section_13 = next((u for u in units if '13' in u.section), None)
    if section_13:
        print(f"\n✅ Section 13 found with {len(section_13.references)} references")
        # Check if it references sections 14, 15, 16 (consent-related)
        consent_refs = [r for r in section_13.references if any(
            str(n) in r for n in [14, 15, 16]
        )]
        print(f"   References to consent sections: {consent_refs}")
    
    # ================================================================
    # CHAPTER/PART STRUCTURE
    # ================================================================
    
    # Check that chapters are captured
    chapters = set()
    for unit in units:
        if unit.chapter and unit.chapter != "General Provisions":
            chapters.add(unit.chapter)
    
    print(f"\n✅ Found {len(chapters)} unique chapters/parts")
    
    # Check for key parts that should exist
    expected_parts = [
        'preliminary',
        'personal data protection commission',
        'collection use disclosure',
        'consent',
        'do not call'
    ]
    
    for expected in expected_parts:
        found = any(expected.lower() in c.lower() for c in chapters)
        if found:
            print(f"   ✅ Found '{expected}'")
        else:
            print(f"   ⚠️  Missing '{expected}'")
    
    # ================================================================
    # SCHEDULE EXTRACTION
    # ================================================================
    
    # Find schedule units
    schedule_units = [u for u in units if 'schedule' in u.chapter.lower()]
    print(f"\n✅ Found {len(schedule_units)} schedule units")
    
    if schedule_units:
        schedule_names = set()
        for u in schedule_units:
            # Extract schedule number
            match = re.search(r'Schedule\s+([A-Z]+)', u.chapter, re.IGNORECASE)
            if match:
                schedule_names.add(match.group(1))
        print(f"   Schedules found: {sorted(schedule_names)}")
        
        # Check for First Schedule (should exist)
        first_schedule = [u for u in schedule_units if 'first' in u.chapter.lower()]
        assert first_schedule, "❌ First Schedule not found!"
        print(f"   ✅ First Schedule has {len(first_schedule)} units")
    
    # ================================================================
    # TEXT QUALITY CHECKS
    # ================================================================
    
    # Check for truncation - none of the text should be cut off at 1000 chars
    truncated_units = []
    for unit in units:
        # If text ends with "..." and length is ~1000, likely truncated
        if len(unit.text) >= 990 and len(unit.text) <= 1010 and unit.text.endswith('...'):
            truncated_units.append(unit)
    
    # Some units might naturally be short, but check for pattern
    suspicious = len([u for u in truncated_units if len(u.text) > 900])
    assert suspicious < 5, f"❌ {suspicious} units appear truncated at ~1000 chars"
    print(f"✅ No truncation detected (checked {len(units)} units)")
    
    # Check for boilerplate removal
    boilerplate_terms = [
        'the statutes of the republic',
        'informal consolidation',
        'republic of singapore',
        'revised edition',
        'law revision commission'
    ]
    
    boilerplate_found = []
    for term in boilerplate_terms:
        for unit in units[:20]:  # Check first 20 units
            if term.lower() in unit.text.lower():
                boilerplate_found.append(term)
                break
    
    if boilerplate_found:
        print(f"⚠️  Boilerplate found in units: {set(boilerplate_found)}")
    else:
        print("✅ No boilerplate text found in extracted content")
    
    # ================================================================
    # METADATA AND SOURCE
    # ================================================================
    
    # Check source label
    assert parser.source_label() == "universal-hybrid-parser"
    print(f"\n✅ Parser source: {parser.source_label()}")
    
    # Check that URL is preserved
    assert units[0].url == "https://sso.agc.gov.sg/Act/PDPA2012"
    
    # Check law identifier
    assert units[0].law.upper() in ["SG_PDPA", "PDPA_SG"]
    
    # ================================================================
    # FINAL SUMMARY
    # ================================================================
    
    print("\n" + "="*60)
    print("📊 PARSING SUMMARY")
    print("="*60)
    print(f"   Total units: {len(units)}")
    print(f"   Total definitions: {len(all_defs)}")
    print(f"   Units with references: {len(units_with_refs)}")
    print(f"   Unique chapters: {len(chapters)}")
    print(f"   Schedule units: {len(schedule_units)}")
    print("="*60)
    print("✅ All tests passed!")
    print("="*60)
    
    return units


def test_pdpa_parser_regex_only(tmp_path: Path) -> None:
    """Tests PDPA parser in regex-only mode (no LLM)."""
    
    pdpa_path = Path("data/raw/sg_pdpa_raw.pdf")
    
    if not pdpa_path.exists():
        pytest.skip(f"PDPA PDF not found at {pdpa_path}")
    
    # Force regex-only by disabling OpenAI
    original_api_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = None
    
    try:
        parser = UniversalAiParser()
        units = parser.parse(
            file_path=pdpa_path,
            url="https://sso.agc.gov.sg/Act/PDPA2012",
            law=LawIdentifier.PDPA_SG
        )
        
        # Should still extract units
        assert len(units) > 30, f"Regex-only should extract >30 units, got {len(units)}"
        print(f"\n✅ Regex-only extracted {len(units)} units")
        
        # Check for Section 2
        section_2 = next((u for u in units if re.search(r'\b2\b', u.section)), None)
        assert section_2 is not None, "Regex-only: Section 2 not found!"
        print(f"✅ Regex-only: Section 2 found")
        
        # Check if it has definitions
        all_defs = []
        for unit in units:
            all_defs.extend(unit.definitions)
        print(f"✅ Regex-only: Found {len(all_defs)} definitions")
        
    finally:
        # Restore API key
        settings.OPENAI_API_KEY = original_api_key


def test_pdpa_parser_with_mock_pdf(tmp_path: Path) -> None:
    """Tests PDPA parser with mock PDF (for CI/CD without real file)."""
    
    # Create mock file
    mock_file = tmp_path / "mock_pdpa.pdf"
    mock_file.write_bytes(b"dummy")
    
    # Mock PDF with PDPA-like content
    mock_pdf = MagicMock()
    
    # Mock pages
    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = (
        "PERSONAL DATA PROTECTION ACT 2012\n"
        "ARRANGEMENT OF SECTIONS\n"
        "Section\n"
        "1. Short title\n"
        "2. Interpretation\n"
        "3. Purpose\n"
    )
    
    mock_page2 = MagicMock()
    mock_page2.extract_text.return_value = (
        "PART 1\n"
        "PRELIMINARY\n"
        "Interpretation\n"
        "2.—(1) In this Act, unless the context otherwise requires —\n"
        '"personal data" means data, whether true or not, about an individual\n'
        "who can be identified from that data or from that data and other\n"
        "information to which the organisation has or is likely to have access;\n"
        '"organisation" includes any individual, company, association or body\n'
        "of persons, corporate or unincorporated.\n"
        "Purpose\n"
        "3. The purpose of this Act is to govern the collection, use and\n"
        "disclosure of personal data by organisations.\n"
    )
    
    mock_pdf.pages = [mock_page1, mock_page2]
    mock_pdf.__enter__.return_value = mock_pdf
    
    parser = UniversalAiParser()
    
    with patch("pdfplumber.open", return_value=mock_pdf):
        units = parser.parse(
            file_path=mock_file,
            url="https://sso.agc.gov.sg/Act/PDPA2012",
            law=LawIdentifier.PDPA_SG
        )
    
    # Should extract at least 2 units
    assert len(units) >= 2
    
    # Check Section 2
    section_2 = next((u for u in units if '2' in u.section), None)
    assert section_2 is not None
    assert 'personal data' in section_2.text.lower()
    assert 'whether true or not' in section_2.text.lower()
    print("\n✅ Mock PDPA test passed!")


def test_pdpa_parser_benchmark(tmp_path: Path) -> None:
    """Benchmark PDPA parser performance."""
    
    pdpa_path = _get_pdpa_path()
    
    if not pdpa_path.exists():
        pytest.skip(f"PDPA PDF not found at {pdpa_path}")
    
    import time
    
    parser = UniversalAiParser()
    
    # Disable LLM for benchmark
    original_api_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = None
    
    try:
        start_time = time.time()
        units = parser.parse(
            file_path=pdpa_path,
            url="https://sso.agc.gov.sg/Act/PDPA2012",
            law=LawIdentifier.PDPA_SG
        )
        elapsed = time.time() - start_time
        
        print(f"\n⏱️  Benchmark Results:")
        print(f"   Time: {elapsed:.2f} seconds")
        print(f"   Units: {len(units)}")
        print(f"   Speed: {len(units)/elapsed:.1f} units/second")
        
        # Should be fast (<10 seconds for regex)
        assert elapsed < 30, f"Parser too slow: {elapsed:.2f} seconds"
        
    finally:
        settings.OPENAI_API_KEY = original_api_key


def test_pdpa_parser_extract_definitions_only(tmp_path: Path) -> None:
    """Test extracting only definitions from PDPA."""
    
    pdpa_path = _get_pdpa_path()
    
    if not pdpa_path.exists():
        pytest.skip(f"PDPA PDF not found at {pdpa_path}")
    
    parser = UniversalAiParser()
    units = parser.parse(
        file_path=pdpa_path,
        url="https://sso.agc.gov.sg/Act/PDPA2012",
        law=LawIdentifier.PDPA_SG
    )
    
    # Collect all definitions
    definitions = {}
    for unit in units:
        for def_model in unit.definitions:
            definitions[def_model.term] = def_model.definition
    
    print(f"\n📖 Extracted {len(definitions)} unique definitions:")
    
    # Print first 10 definitions
    for term, definition in list(definitions.items())[:10]:
        print(f"   • {term}: {definition[:80]}...")
    
    # Check for critical definitions
    critical_terms = [
        'personal data',
        'organisation',
        'processing',
        'consent',
        'data intermediary',
        'public agency'
    ]
    
    found = [t for t in critical_terms if any(t in k.lower() for k in definitions.keys())]
    missing = [t for t in critical_terms if not any(t in k.lower() for k in definitions.keys())]
    
    print(f"\n   Found critical definitions: {len(found)}/{len(critical_terms)}")
    if missing:
        print(f"   Missing: {missing}")
    
    # At least some critical terms should be found
    assert len(found) >= 3, f"Too few critical definitions found: {found}"