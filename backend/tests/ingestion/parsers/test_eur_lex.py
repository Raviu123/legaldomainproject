"""Unit tests for the EUR-Lex HTML parser.
"""

from pathlib import Path
from app.core.constants import LawName
from app.ingestion.parsers.eur_lex import parse_eur_lex_html


def test_parse_eur_lex_html(tmp_path: Path) -> None:
    """Tests parsing a small EUR-Lex HTML mock file."""
    # Create a small mock HTML document
    mock_html = """
    <html>
    <body>
        <p>CHAPTER I</p>
        <p>General provisions</p>
        <p>Article 1</p>
        <p>Subject-matter and objectives</p>
        <p>1. This Regulation lays down rules relating to the protection of natural persons.</p>
        <table>
            <tbody>
                <tr>
                    <td><p>(1)</p></td>
                    <td><p>‘personal data’ means any information relating to an identified person;</p></td>
                </tr>
            </tbody>
        </table>
        <p>Article 2</p>
        <p>Material scope</p>
        <p>This Regulation applies to the processing of personal data.</p>
    </body>
    </html>
    """
    
    # Save mock HTML to temp file
    file_path = tmp_path / "gdpr_mock.html"
    file_path.write_text(mock_html, encoding="utf-8")
    
    # Parse mock HTML
    units = parse_eur_lex_html(
        file_path=file_path,
        url="https://eur-lex.europa.eu/mock-gdpr",
        law_name=LawName.GDPR
    )
    
    # Verify results
    # We expect 2 articles: Article 1 (which includes the definitions row text) and Article 2
    assert len(units) == 2
    
    art1 = units[0]
    assert art1.id == "gdpr:art1"
    assert art1.law == "GDPR"
    assert art1.chapter == "Chapter I - General provisions"
    assert art1.article == "Article 1"
    assert art1.title == "Subject-matter and objectives"
    assert "lays down rules relating to" in art1.text
    # Check that the table row is merged into the same block
    assert "‘personal data’ means" in art1.text
    
    art2 = units[1]
    assert art2.id == "gdpr:art2"
    assert art2.article == "Article 2"
    assert art2.title == "Material scope"
    assert "applies to the processing" in art2.text
