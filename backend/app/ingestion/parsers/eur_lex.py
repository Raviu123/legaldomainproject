"""EUR-Lex HTML parser.

Parses GDPR (and other EUR-Lex laws) from raw HTML into normalized LegalUnit models.
"""

import re
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup, Tag

from app.core.constants import LawIdentifier
from app.core.logging import logger
from app.models.legal_unit import LegalUnit


def parse_eur_lex_html(
    file_path: Path, url: str, law_name: LawIdentifier = LawIdentifier.GDPR
) -> List[LegalUnit]:
    """Parses a EUR-Lex HTML file into a list of LegalUnit objects.

    Args:
        file_path: Path to the raw HTML file.
        url: The source URL of the document.
        law_name: The name of the law (defaults to GDPR).

    Returns:
        List[LegalUnit]: List of parsed legal units.
    """
    logger.info(f"Parsing EUR-Lex HTML file: {file_path}")

    if not file_path.exists():
        raise FileNotFoundError(f"Source file not found: {file_path}")

    html_content = file_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_content, "lxml")

    body = soup.body if soup.body else soup

    # Extract blocks in order, treating tr as a single block to keep columns together
    blocks: List[str] = []

    def extract_blocks_dfs(element) -> None:
        if not isinstance(element, Tag):
            return

        # Leaf block elements that we want to keep together
        if element.name in ["tr", "p", "h1", "h2", "h3", "h4", "h5", "h6"]:
            text = element.get_text(separator=" ", strip=True)
            if text:
                blocks.append(text)
            return  # Do not recurse into children of a block leaf (keeps cells in a row together)

        # Treat leaf-like divs as block elements
        if element.name == "div":
            if not element.find(["p", "tr", "div", "h1", "h2", "h3", "h4", "h5", "h6"]):
                text = element.get_text(separator=" ", strip=True)
                if text:
                    blocks.append(text)
                return

        # For container tags, recurse into children
        for child in element.children:
            extract_blocks_dfs(child)

    extract_blocks_dfs(body)

    legal_units: List[LegalUnit] = []

    current_chapter = "Preamble"
    current_article_num = None
    current_article_title = None
    current_article_text_lines = []

    in_recitals = True

    # Patterns
    chapter_pattern = re.compile(r"^\s*CHAPTER\s+([IVXLCDM]+)\s*$", re.IGNORECASE)
    chapter_inline_pattern = re.compile(
        r"^\s*CHAPTER\s+([IVXLCDM]+)\s*[-–—:]\s*(.+)$", re.IGNORECASE
    )

    article_pattern = re.compile(r"^\s*Article\s+(\d+)\s*$", re.IGNORECASE)
    article_inline_pattern = re.compile(r"^\s*Article\s+(\d+)\s*[-–—:]\s*(.+)$", re.IGNORECASE)

    # Recital pattern: matches "(1) Text..." or "(1)Text..."
    recital_pattern = re.compile(r"^\s*\((\d+)\)\s*(.+)$")

    def flush_article():
        nonlocal current_article_num, current_article_title, current_article_text_lines
        if current_article_num is not None:
            full_text = "\n".join(current_article_text_lines).strip()
            if full_text:
                art_id = f"{law_name.value.lower()}:art{current_article_num}"
                unit = LegalUnit(
                    id=art_id,
                    law=law_name.value,
                    chapter=current_chapter,
                    article=f"Article {current_article_num}",
                    title=current_article_title or f"Article {current_article_num}",
                    text=full_text,
                    source="eur-lex",
                    url=url,
                )
                legal_units.append(unit)
            current_article_num = None
            current_article_title = None
            current_article_text_lines = []

    skip_next_for_title = False

    for text in blocks:
        # Check for chapter
        chap_match = chapter_pattern.match(text)
        chap_inline_match = chapter_inline_pattern.match(text)

        if chap_match or chap_inline_match:
            flush_article()
            in_recitals = False

            if chap_inline_match:
                chap_num = chap_inline_match.group(1)
                chap_title = chap_inline_match.group(2)
                current_chapter = f"Chapter {chap_num} - {chap_title}"
            else:
                chap_num = chap_match.group(1)
                current_chapter = f"Chapter {chap_num}"
                skip_next_for_title = "chapter"
            continue

        if skip_next_for_title == "chapter":
            current_chapter = f"{current_chapter} - {text}"
            skip_next_for_title = False
            continue

        # Check for article
        art_match = article_pattern.match(text)
        art_inline_match = article_inline_pattern.match(text)

        if art_match or art_inline_match:
            flush_article()
            in_recitals = False

            if art_inline_match:
                current_article_num = art_inline_match.group(1)
                current_article_title = art_inline_match.group(2)
            else:
                current_article_num = art_match.group(1)
                skip_next_for_title = "article"
            continue

        if skip_next_for_title == "article":
            current_article_title = text
            skip_next_for_title = False
            continue

        # Handle recitals
        if in_recitals:
            rec_match = recital_pattern.match(text)
            if rec_match:
                rec_num = rec_match.group(1)
                rec_text = rec_match.group(2).strip()
                if rec_text:  # Ensure we don't save empty recitals
                    rec_id = f"{law_name.value.lower()}:recital{rec_num}"
                    unit = LegalUnit(
                        id=rec_id,
                        law=law_name.value,
                        chapter="Recitals",
                        article=f"Recital {rec_num}",
                        title=f"Recital {rec_num}",
                        text=rec_text,
                        source="eur-lex",
                        url=url,
                    )
                    legal_units.append(unit)
                    continue

        # Accumulate text for active article
        if current_article_num is not None:
            current_article_text_lines.append(text)

    flush_article()

    logger.info(f"Finished parsing EUR-Lex HTML. Extracted {len(legal_units)} units.")
    return legal_units
