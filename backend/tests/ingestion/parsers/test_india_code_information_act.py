"""Unit tests for the India Code IT Intermediary Rules parser.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.constants import LawIdentifier
from app.ingestion.parsers.india_code_information_act import ItIntermediaryRules2021Parser
from app.extraction.structure_extractor import extract_definitions_from_it_rules_rule2


def test_it_intermediary_rules_parser(tmp_path: Path) -> None:
    """Tests parsing mock IT Intermediary Rules PDF text using the state machine."""
    # Create a dummy mock file so that exists() check passes
    mock_file = tmp_path / "mock_it_rules.pdf"
    mock_file.write_bytes(b"dummy")

    # Mock PDF structure
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = (
        "THE INFORMATION TECHNOLOGY (INTERMEDIARY GUIDELINES\n"
        "AND DIGITAL MEDIA ETHICS CODE) RULES, 2021\n"
        "PART I\n"
        "PRELIMINARY\n"
        "1. Short Title and Commencement.—(1) These rules may be called the Information\n"
        "Technology (Intermediary Guidelines and Digital Media Ethics Code) Rules, 2021.\n"
        "(2) They shall come into force on the date of their publication.\n"
        "2. Definitions.—(1) In these rules, unless the context otherwise requires,—\n"
        '(a) "Act" means the Information Technology Act, 2000 (21 of 2000);\n'
        '(b) "advisory" means an advisory issued by the Ministry;\n'
    )

    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf

    parser = ItIntermediaryRules2021Parser()

    with patch("pdfplumber.open", return_value=mock_pdf):
        units = parser.parse(
            file_path=mock_file,
            url="https://www.meity.gov.in/rules-and-acts",
            law=LawIdentifier.IT_INTERMEDIARY_RULES_2021
        )

    # We expect 2 units: Rule 1, and Rule 2
    assert len(units) == 2

    rule1 = units[0]
    assert rule1.id == "it_intermediary_rules_2021:rule_1"
    assert rule1.law == "IT_INTERMEDIARY_RULES_2021"
    assert rule1.chapter == "Part I - PRELIMINARY"
    assert rule1.article == "Rule 1"
    assert rule1.title == "Short Title and Commencement"
    assert "These rules may be called" in rule1.text

    rule2 = units[1]
    assert rule2.id == "it_intermediary_rules_2021:rule_2"
    assert rule2.law == "IT_INTERMEDIARY_RULES_2021"
    assert rule2.article == "Rule 2"
    assert rule2.title == "Definitions"
    assert '(a) "Act" means' in rule2.text

    # Verify that the definition extractor successfully pulls definitions from Rule 2
    defs = extract_definitions_from_it_rules_rule2(rule2.text)
    assert len(defs) == 2
    assert defs[0].term == "Act"
    assert defs[0].definition == "the Information Technology Act, 2000 (21 of 2000)"
    assert defs[1].term == "advisory"
    assert defs[1].definition == "an advisory issued by the Ministry"
