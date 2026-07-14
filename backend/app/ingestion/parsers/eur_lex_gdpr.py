"""EUR-Lex HTML parser for GDPR (and compatible EUR-Lex layouts).

Implements BaseLegalParser for the GDPR source HTML retrieved from EUR-Lex.
The same parser can be used as a base for AI Act and other EUR-Lex regulations
by subclassing and overriding source_label() / any layout overrides.

Source: https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng
Format: HTML (lxml)
"""

import re
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup, Tag

from app.core.constants import LawIdentifier
from app.core.logging import logger
from app.ingestion.parsers.base import BaseLegalParser
from app.models.legal_unit import LegalUnit


class EurLexGdprParser(BaseLegalParser):
    """Parses GDPR HTML from EUR-Lex into LegalUnit objects.

    Handles the two-column EUR-Lex HTML layout, extracting:
    - Recitals (preamble numbered paragraphs)
    - Chapters (CHAPTER I, II, ... with roman numerals)
    - Articles (Article 1, 2, ...) with optional inline titles
    """

    def source_label(self) -> str:
        return "eur-lex"

    def parse(
        self,
        file_path: Path,
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Parse EUR-Lex GDPR HTML file into LegalUnit objects.

        Args:
            file_path: Path to the cached HTML file.
            url: Source URL for citation.
            law: Must be LawIdentifier.GDPR (or a compatible EUR-Lex law).

        Returns:
            List of LegalUnit objects (Recitals + Articles).

        Raises:
            FileNotFoundError: If file_path does not exist.
            ValueError: If the parsed document yields zero legal units.
        """
        logger.info(f"[EurLexGdprParser] Parsing: {file_path}")

        if not file_path.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")

        html_content = file_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "lxml")
        body = soup.body if soup.body else soup

        blocks = self._extract_text_blocks(body)
        units = self._parse_blocks(blocks, url, law)

        if not units:
            raise ValueError(
                f"[EurLexGdprParser] Parsed zero legal units from {file_path}. "
                "Check that the HTML structure matches the expected EUR-Lex format."
            )

        logger.info(f"[EurLexGdprParser] Extracted {len(units)} legal units.")
        return units

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_text_blocks(self, body: Tag) -> List[str]:
        """DFS traversal of HTML body into sequential flat text blocks."""
        blocks: List[str] = []

        def _dfs(element: Tag) -> None:
            if not isinstance(element, Tag):
                return
            # Leaf block-level elements — capture together, don't recurse
            if element.name in ["tr", "p", "h1", "h2", "h3", "h4", "h5", "h6"]:
                text = element.get_text(separator=" ", strip=True)
                if text:
                    blocks.append(text)
                return
            # Leaf-like divs (no nested block elements)
            if element.name == "div":
                if not element.find(["p", "tr", "div", "h1", "h2", "h3", "h4", "h5", "h6"]):
                    text = element.get_text(separator=" ", strip=True)
                    if text:
                        blocks.append(text)
                    return
            for child in element.children:
                _dfs(child)

        _dfs(body)
        return blocks

    def _parse_blocks(
        self,
        blocks: List[str],
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """State-machine pass over extracted blocks to build LegalUnit objects."""
        law_prefix = law.value  # e.g. 'gdpr'

        # --- Compiled patterns ---
        chapter_pattern = re.compile(r"^\s*CHAPTER\s+([IVXLCDM]+)\s*$", re.IGNORECASE)
        chapter_inline = re.compile(
            r"^\s*CHAPTER\s+([IVXLCDM]+)\s*[-\u2013\u2014:]\s*(.+)$", re.IGNORECASE
        )
        article_pattern = re.compile(r"^\s*Article\s+(\d+)\s*$", re.IGNORECASE)
        article_inline = re.compile(
            r"^\s*Article\s+(\d+)\s*[-\u2013\u2014:]\s*(.+)$", re.IGNORECASE
        )
        recital_pattern = re.compile(r"^\s*\((\d+)\)\s*(.+)$")

        units: List[LegalUnit] = []
        current_chapter = "Preamble"
        current_article_num: str | None = None
        current_article_title: str | None = None
        current_article_lines: List[str] = []
        in_recitals = True
        skip_next_for: str | None = None  # 'chapter' | 'article' | None

        def flush_article() -> None:
            nonlocal current_article_num, current_article_title, current_article_lines
            if current_article_num is not None:
                full_text = "\n".join(current_article_lines).strip()
                if full_text:
                    art_id = f"{law_prefix}:art{current_article_num}"
                    units.append(
                        LegalUnit(
                            id=art_id,
                            law=law.value.upper(),
                            chapter=current_chapter,
                            article=f"Article {current_article_num}",
                            title=current_article_title or f"Article {current_article_num}",
                            text=full_text,
                            source=self.source_label(),
                            url=url,
                        )
                    )
                current_article_num = None
                current_article_title = None
                current_article_lines = []

        for text in blocks:
            # --- Chapter detection ---
            if m := chapter_pattern.match(text):
                flush_article()
                in_recitals = False
                current_chapter = f"Chapter {m.group(1)}"
                skip_next_for = "chapter"
                continue
            if m := chapter_inline.match(text):
                flush_article()
                in_recitals = False
                current_chapter = f"Chapter {m.group(1)} - {m.group(2)}"
                skip_next_for = None
                continue

            if skip_next_for == "chapter":
                current_chapter = f"{current_chapter} - {text}"
                skip_next_for = None
                continue

            # --- Article detection ---
            if m := article_pattern.match(text):
                flush_article()
                in_recitals = False
                current_article_num = m.group(1)
                skip_next_for = "article"
                continue
            if m := article_inline.match(text):
                flush_article()
                in_recitals = False
                current_article_num = m.group(1)
                current_article_title = m.group(2)
                skip_next_for = None
                continue

            if skip_next_for == "article":
                current_article_title = text
                skip_next_for = None
                continue

            # --- Recital detection ---
            if in_recitals:
                if m := recital_pattern.match(text):
                    rec_num = m.group(1)
                    rec_text = m.group(2).strip()
                    if rec_text:
                        rec_id = f"{law_prefix}:recital{rec_num}"
                        units.append(
                            LegalUnit(
                                id=rec_id,
                                law=law.value.upper(),
                                chapter="Recitals",
                                article=f"Recital {rec_num}",
                                title=f"Recital {rec_num}",
                                text=rec_text,
                                source=self.source_label(),
                                url=url,
                            )
                        )
                    continue

            # --- Accumulate article body text ---
            if current_article_num is not None:
                current_article_lines.append(text)

        flush_article()
        return units
