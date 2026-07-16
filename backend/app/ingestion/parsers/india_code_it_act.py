"""PDF parser for India's Information Technology Act, 2000.

Source : https://www.indiacode.nic.in/bitstream/123456789/1999/1/A2000-21%20%281%29.pdf
Format : PDF
Tool   : pdfplumber
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from app.core.constants import LawIdentifier
from app.core.logging import logger
from app.ingestion.parsers.base import BaseLegalParser
from app.models.legal_unit import LegalUnit

# ---------------------------------------------------------------------------
# Regex patterns for Indian Legislation (India Code)
# ---------------------------------------------------------------------------

# Page headers, running titles, and standalone page numbers
_HEADER_FOOTER_PATTERNS = [
    re.compile(r"^THE\s+INFORMATION\s+TECHNOLOGY\s+ACT,\s*2000", re.IGNORECASE),
    re.compile(r"^ACT\s+NO\.\s+21\s+OF\s+2000", re.IGNORECASE),
    re.compile(r"^ARRANGEMENT\s+OF\s+SECTIONS", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),  # Standalone page numbers
]

# Footnote lines at the bottom of pages (e.g., "1. Subs. by Act 10 of 2009...")
_FOOTNOTE_LINE_RE = re.compile(
    r"^\s*(?:\*\s*|\d+\.\s+)(?:Subs\.|Ins\.|Omitted|Added|Renumbered|w\.e\.f\.|vide\s+notification|ibid|Act\s+\d+\s+of)",
    re.IGNORECASE,
)

# Chapters: e.g. "CHAPTER I", "CHAPTER IV — SECURE ELECTRONIC RECORDS"
_CHAPTER_RE = re.compile(
    r"^\s*CHAPTER\s+([IVXLCDM\d]+)\s*(?:[—\-–]\s*(.+))?$",
    re.IGNORECASE,
)
_CHAPTER_TITLE_RE = re.compile(r"^\s*([A-Z][A-Z\s,–\-—]+[A-Z])\s*$")

# Schedules: e.g. "THE FIRST SCHEDULE", "THE SECOND SCHEDULE"
_SCHEDULE_RE = re.compile(r"^\s*(THE\s+)?([A-Z]+\s+SCHEDULE)\s*(?:[—\-–]\s*(.+))?$", re.IGNORECASE)

# Sections: e.g. "1. Short title...", "6A. Delivery...", "12[70B. Cyber Security..."
# Upgraded to handle multi-letter suffixes (e.g., 69A, 70B) and multiple footnote markers
_SECTION_RE = re.compile(r"^\s*(?:\d+\[)*(?:\*\s*)?(\d+[A-Z]*)\.\s+(.*)")

# Sub-structures upgraded to capture Indian legal numbering quirks:
# - Subsections: (1), (1A), (2B)
# - Clauses: (a), (z), (za), (zb), (zc) [Crucial for Section 2 definitions]
# - Sub-clauses: (i), (iv), (ia), (iia), (ix)
_SUBSECTION_RE = re.compile(r"^\s*\(([0-9]+[A-Z]*)\)\s+(.*)")
_CLAUSE_RE = re.compile(r"^\s*\(([a-z]+)\)\s+(.*)")
_SUBCLAUSE_RE = re.compile(r"^\s*\(((?:i|v|x)+[a-z]?)\)\s+(.*)", re.IGNORECASE)


class IndiaCodeItActParser(BaseLegalParser):
    """Parses the IT Act 2000 PDF from India Code into LegalUnit objects."""

    def source_label(self) -> str:
        return "india-code"

    def parse(
        self,
        file_path: Path,
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Parse the Information Technology Act PDF into LegalUnit objects.

        Args:
            file_path: Path to the cached PDF.
            url: Seed URL.
            law: The LawIdentifier enum.

        Returns:
            List[LegalUnit]: Extracted units.
        """
        try:
            import pdfplumber
        except ImportError as exc:
            raise ImportError(
                "pdfplumber is required to parse PDF files. Install it with: pip install pdfplumber"
            ) from exc

        if not file_path.exists():
            raise FileNotFoundError(f"IT Act PDF not found: {file_path}")

        logger.info(f"[ItActParser] Opening PDF: {file_path}")

        raw_lines: List[str] = []
        in_toc = True

        with pdfplumber.open(str(file_path)) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"[ItActParser] PDF has {total_pages} pages.")

            for page_idx, page in enumerate(pdf.pages):
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                lines = text.splitlines()

                # Dynamic TOC Skipping: Skip pages until we hit the actual Act body
                if in_toc:
                    page_text_combined = " ".join(lines)
                    if "ARRANGEMENT OF SECTIONS" in page_text_combined and page_idx < 5:
                        continue
                    # Check for enacting formula or Chapter I to exit TOC mode
                    if any(
                        "BE it enacted by Parliament" in l or _CHAPTER_RE.match(l)
                        for l in lines
                    ):
                        in_toc = False
                        logger.info(f"[ItActParser] Exited Table of Contents at page {page_idx + 1}.")
                    else:
                        continue

                raw_lines.extend(lines)

        logger.info(f"[ItActParser] Extracted {len(raw_lines)} raw lines.")
        clean_lines = self._clean_lines(raw_lines)
        logger.info(f"[ItActParser] {len(clean_lines)} lines remaining after filtering.")

        units = self._state_machine(clean_lines, url, law)

        if not units:
            raise ValueError("[ItActParser] Parsed zero legal units. Check PDF layout or regex rules.")

        logger.info(f"[ItActParser] Successfully extracted {len(units)} legal units.")
        return units

    # ------------------------------------------------------------------
    # Cleaning helpers
    # ------------------------------------------------------------------

    def _is_noise_or_footnote(self, line: str) -> bool:
        """Returns True if the line is running header/footer or bottom-of-page footnote."""
        stripped = line.strip()
        if not stripped:
            return True

        # Check against running page headers and page numbers
        for pattern in _HEADER_FOOTER_PATTERNS:
            if pattern.match(stripped):
                return True

        # Check for bottom-of-page amendment footnotes
        # We check specific regex patterns rather than raw keywords to avoid skipping
        # valid legal text that happens to contain words like "Ministry" or "w.e.f."
        if _FOOTNOTE_LINE_RE.match(stripped):
            return True

        return False

    def _clean_lines(self, raw_lines: List[str]) -> List[str]:
        """Filters out noise and normalizes whitespace while preserving indent structure."""
        cleaned: List[str] = []
        for line in raw_lines:
            if self._is_noise_or_footnote(line):
                continue
            # Normalize whitespace while keeping up to 4 spaces of indentation context
            leading = len(line) - len(line.lstrip())
            normalized = " " * min(leading, 4) + " ".join(line.split())
            if normalized.strip():
                cleaned.append(normalized)
        return cleaned

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _split_section_title(self, rest: str) -> Tuple[str, str]:
        """Separates the section title from the section body content."""
        # Check standard em-dash, en-dash, hyphens, and PDF replacement char \uFFFD
        for sep in [".—", ". --", ". -", " — ", " – ", "\uFFFD"]:
            if sep in rest:
                parts = rest.split(sep, 1)
                return parts[0].strip().rstrip("."), parts[1].strip()

        # Fallback: First period followed by a subsection like (1) or capital letter
        m = re.search(r"\.\s+(?=\(\d+\)|[A-Z])", rest)
        if m:
            idx = m.start()
            title = rest[:idx].strip()
            body = rest[idx + 1:].strip()
            return title, body

        return rest, ""

    def _clean_content(self, text: str) -> str:
        """Cleans replacement characters, footnote syntax, and whitespace."""
        # Replace PDF reader replacement characters for quotes/dashes
        text = text.replace("\uFFFD", '"')
        
        # Recursively remove footnote syntax like 1[electronic signature] -> electronic signature
        # Also handles omitted markers like 1[***] or 2[Omitted.]
        while re.search(r"\d+\[([^\]]*)\]", text):
            text = re.sub(r"\d+\[([^\]]*)\]", r"\1", text)
            
        # Normalize horizontal whitespace while preserving line breaks
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        return "\n".join(lines).strip()

    def _state_machine(
        self,
        lines: List[str],
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Walks clean lines to assemble preamble, chapters, sections, and schedules."""
        units: List[LegalUnit] = []
        law_prefix = law.value  # e.g., "it_act"

        current_chapter: str = "Preliminary"
        pending_chapter_title: bool = False
        current_section_num: Optional[str] = None
        current_section_title: str = ""
        current_section_lines: List[str] = []

        in_preamble = False
        preamble_lines: List[str] = []

        def flush_section() -> None:
            nonlocal current_section_num, current_section_title, current_section_lines
            if current_section_num is None:
                return

            body_text = "\n".join(current_section_lines).strip()
            body_text = self._clean_content(body_text)

            full_text = (
                f"{current_section_title}\n{body_text}"
                if current_section_title
                else body_text
            )

            # Prefix schedule items differently if we are inside a Schedule
            if "SCHEDULE" in current_chapter.upper():
                unit_id = f"{law_prefix}:sched_{current_section_num.lower()}"
                article_label = f"Schedule Item {current_section_num}"
            else:
                unit_id = f"{law_prefix}:sec_{current_section_num.lower()}"
                article_label = f"Section {current_section_num}"

            units.append(
                LegalUnit(
                    id=unit_id,
                    law="IT_ACT",
                    chapter=current_chapter,
                    article=article_label,
                    title=current_section_title or article_label,
                    text=full_text,
                    source=self.source_label(),
                    url=url,
                )
            )

            current_section_num = None
            current_section_title = ""
            current_section_lines = []

        for line_raw in lines:
            line = line_raw.strip()
            if not line:
                continue

            # --- Detect Preamble (Enacting Formula) ---
            if line.lower().startswith("an act to") or "be it enacted by parliament" in line.lower():
                in_preamble = True
                preamble_lines.append(line_raw)
                continue

            # --- Detect Chapter Boundary ---
            if m := _CHAPTER_RE.match(line):
                flush_section()
                in_preamble = False
                roman = m.group(1).upper()
                inline_title = (m.group(2) or "").strip()
                if inline_title:
                    current_chapter = f"Chapter {roman} - {inline_title}"
                    pending_chapter_title = False
                else:
                    current_chapter = f"Chapter {roman}"
                    pending_chapter_title = True
                continue

            # --- Detect Chapter Title on separate line ---
            if pending_chapter_title:
                if _CHAPTER_TITLE_RE.match(line) and not _SECTION_RE.match(line):
                    current_chapter = f"{current_chapter} - {line}"
                    pending_chapter_title = False
                    continue
                pending_chapter_title = False

            # --- Detect Schedule Boundary ---
            if m := _SCHEDULE_RE.match(line):
                flush_section()
                in_preamble = False
                sched_name = m.group(2).strip().title()
                inline_title = (m.group(3) or "").strip()
                current_chapter = f"{sched_name} - {inline_title}" if inline_title else sched_name
                continue

            # --- Detect Section / Schedule Item Boundary ---
            if m := _SECTION_RE.match(line):
                # Guard against matching numbered lists inside an active section body
                # Unless the number jumped sequentially or is an alphanumeric section (e.g., 6A, 69B)
                potential_sec = m.group(1)
                
                flush_section()
                in_preamble = False
                current_section_num = potential_sec
                rest = m.group(2).strip()

                title, body = self._split_section_title(rest)
                current_section_title = self._clean_content(title)
                current_section_lines = [body] if body else []
                continue

            # --- Accumulate content into current Section ---
            if current_section_num is not None:
                # Apply structural indentations for readability
                if _SUBSECTION_RE.match(line):
                    current_section_lines.append(f"\n{line}")
                elif _CLAUSE_RE.match(line):
                    current_section_lines.append(f"  {line}")
                elif _SUBCLAUSE_RE.match(line):
                    current_section_lines.append(f"    {line}")
                else:
                    current_section_lines.append(line)
                continue

            # --- Accumulate content into Preamble ---
            if in_preamble:
                preamble_lines.append(line_raw)

        # Flush the final section or schedule item
        flush_section()

        # Emit Preamble as the first LegalUnit if captured
        if preamble_lines:
            preamble_text = " ".join(preamble_lines).strip()
            preamble_text = self._clean_content(preamble_text)
            if preamble_text:
                units.insert(
                    0,
                    LegalUnit(
                        id=f"{law_prefix}:preamble",
                        law="IT_ACT",
                        chapter="Preamble",
                        article="Preamble",
                        title="Long Title and Enacting Formula",
                        text=preamble_text,
                        source=self.source_label(),
                        url=url,
                    ),
                )

        return units