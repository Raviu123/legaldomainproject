from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.constants import LawIdentifier
from app.ingestion.parsers.india_code_dpdp_rules import IndiaCodeDpdpRulesParser
from app.extraction.structure_extractor import extract_definitions_from_dpdp_rules_rule2


def test_dpdp_rules_parser(tmp_path: Path) -> None:
    """Tests parsing mock DPDP Rules 2025 PDF text using the state machine."""
    # Create a dummy mock file so that exists() check passes
    mock_file = tmp_path / "mock_rules.pdf"
    mock_file.write_bytes(b"dummy")

    # Mock PDF structure
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = (
        "MINISTRY OF ELECTRONICS AND INFORMATION TECHNOLOGY\n"
        "NOTIFICATION\n"
        "New Delhi, the 13th November, 2025\n"
        "G.S.R. 123(E).—In exercise of the powers conferred by section 40...\n"
        "CHAPTER I\n"
        "PRELIMINARY\n"
        "1. Short title and commencement.—(1) These rules may be called the Digital Personal Data\n"
        "Protection Rules, 2025.\n"
        "(2) Rules 1, 2 and 17 to 21 shall come into force...\n"
        "2. Definitions.—(1) In these rules, unless the context otherwise requires,—\n"
        "(a) \u201cAct\u201d means the Digital Personal Data Protection Act, 2023 (22 of 2023);\n"
        "(b) \u201cUser account\u201d means the online account registered by the Data Principal\n"
        "with the Data Fiduciary;\n"
    )

    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf

    parser = IndiaCodeDpdpRulesParser()

    with patch("pdfplumber.open", return_value=mock_pdf):
        units = parser.parse(
            file_path=mock_file,
            url="https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf",
            law=LawIdentifier.DPDP_RULES
        )

    # We expect 3 units: Preamble, Rule 1, and Rule 2
    assert len(units) == 3

    preamble = units[0]
    assert preamble.id == "dpdp_rules:preamble"
    assert preamble.chapter == "Preamble"
    assert "In exercise of the powers" in preamble.text

    rule1 = units[1]
    assert rule1.id == "dpdp_rules:rule1"
    assert rule1.chapter == "Chapter I - PRELIMINARY"
    assert rule1.article == "Rule 1"
    assert rule1.title == "Short title and commencement"
    assert 'These rules may be called' in rule1.text

    rule2 = units[2]
    assert rule2.id == "dpdp_rules:rule2"
    assert rule2.article == "Rule 2"
    assert rule2.title == "Definitions"
    assert '(a) "Act" means' in rule2.text

    # Verify that the definition extractor successfully pulls definitions from Rule 2
    defs = extract_definitions_from_dpdp_rules_rule2(rule2.text)
    assert len(defs) == 2
    assert defs[0].term == "Act"
    assert defs[0].definition == "the Digital Personal Data Protection Act, 2023 (22 of 2023)"
    assert defs[1].term == "User account"
    assert defs[1].definition == "the online account registered by the Data Principal with the Data Fiduciary"
