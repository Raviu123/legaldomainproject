"""Unit tests for the India Code IT Act parser.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.constants import LawIdentifier
from app.ingestion.parsers.india_code_it_act import IndiaCodeItActParser


def test_it_act_parser(tmp_path: Path) -> None:
    """Tests parsing mock IT Act PDF text using the state machine."""
    # Create a dummy mock file so that exists() check passes
    mock_file = tmp_path / "mock_path.pdf"
    mock_file.write_bytes(b"dummy")

    # Mock PDF structure with 5 pages (first 4 pages are TOC, 5th is the actual Act content)
    mock_pdf = MagicMock()
    
    mock_toc_page = MagicMock()
    mock_toc_page.extract_text.return_value = (
        "THE INFORMATION TECHNOLOGY ACT, 2000\n"
        "ARRANGEMENT OF SECTIONS\n"
        "SECTIONS\n"
        "1. Short title, extent, commencement and application.\n"
    )
    
    mock_content_page = MagicMock()
    mock_content_page.extract_text.return_value = (
        "THE INFORMATION TECHNOLOGY ACT, 2000\n"
        "ACT NO. 21 OF 2000\n"
        "An Act to provide legal recognition for transactions carried out by means of electronic data...\n"
        "BE it enacted by Parliament in the Fifty-first Year of the Republic of India as follows:\n"
        "CHAPTER 1\n"
        "PRELIMINARY\n"
        "1. Short title, extent, commencement and application.\uFFFD(1) This Act may be called the Information\n"
        "Technology Act, 2000.\n"
        "(2) It shall extend to the whole of India.\n"
        "2. Definitions.\uFFFD(1) In this Act, unless the context otherwise requires,\uFFFD\n"
        "(a) \uFFFDaccess\uFFFD means instructing...\n"
        "(b) \uFFFDaddressee\uFFFD means a person...\n"
        "1. 17th October, 2000, vide notification No. G.S.R. 788 (E) (w.e.f. 17-10-2000).\n"
        "2. Subs. by Act 10 of 2009, s. 3, for sub-section (4) (w.e.f. 27-10-2009).\n"
    )
    
    mock_pdf.pages = [
        mock_toc_page,
        mock_toc_page,
        mock_toc_page,
        mock_toc_page,
        mock_content_page,
    ]
    mock_pdf.__enter__.return_value = mock_pdf
    
    parser = IndiaCodeItActParser()
    
    with patch("pdfplumber.open", return_value=mock_pdf):
        units = parser.parse(
            file_path=mock_file,
            url="https://www.indiacode.nic.in/handle/123456789/1999",
            law=LawIdentifier.IT_ACT
        )
        
    # We expect 3 units: Preamble, Section 1, Section 2
    assert len(units) == 3
    
    # 1. Preamble
    preamble = units[0]
    assert preamble.id == "it_act:preamble"
    assert preamble.law == "IT_ACT"
    assert preamble.chapter == "Preamble"
    assert preamble.article == "Preamble"
    assert preamble.title == "Long Title"
    assert "An Act to provide" in preamble.text
    
    # 2. Section 1
    sec1 = units[1]
    assert sec1.id == "it_act:sec1"
    assert sec1.chapter == "Chapter 1 - PRELIMINARY"
    assert sec1.article == "Section 1"
    assert sec1.title == "Short title, extent, commencement and application"
    assert "This Act may be called" in sec1.text
    assert "It shall extend to the whole of India." in sec1.text
    # Check that footnote boilerplate is filtered
    assert "17th October, 2000" not in sec1.text
    
    # 3. Section 2
    sec2 = units[2]
    assert sec2.id == "it_act:sec2"
    assert sec2.article == "Section 2"
    assert sec2.title == "Definitions"
    # Ensure quotes are replaced with standard double quotes
    assert '(a) "access" means' in sec2.text
    assert '(b) "addressee" means' in sec2.text
    assert "Subs. by Act 10 of 2009" not in sec2.text
