"""PDF parser for India's Digital Personal Data Protection Act, 2023.

Source : https://www.meity.gov.in/static/uploads/2024/06/2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf
Format : PDF (gazette notification — MeitY)
Tool   : pdfplumber

Layout notes (empirically observed from this specific PDF):
  - Gazette header lines appear on every page:
      "THE GAZETTE OF INDIA EXTRAORDINARY", "PART II—SEC. 1", page-numbers, date strings
  - Act numbering line: "ACT NO. 22 OF 2023"
  - Blank-line separators are unreliable — use pattern matching, not blank-line splits.
  - Chapter headings:    "CHAPTER I" (upper-case, standalone line, sometimes followed by title)
  - Section headings:   "1.", "2.", "3." ... (digit followed by full-stop at start of line)
  - Sub-sections:        "(1)", "(2)" — numeric in parentheses
  - Clauses:             "(a)", "(b)", "(c)" — alpha in parentheses
  - Sub-clauses:         "(i)", "(ii)" — roman numerals in parentheses
  - Explanation blocks:  Lines starting with "Explanation" or "Explanation.—"
  - Provisos:            Lines starting with "Provided that" or "Provided further"
  - All of sub-section / clause / sub-clause text belongs to the PARENT Section node.

ID scheme:
  dpdp:sec1, dpdp:sec2, ... dpdp:sec44
  (Section 2 sub-clauses that are definitions are split into dpdp:def_<term>)
"""

import re
from pathlib import Path
from typing import List, Optional

from app.core.constants import LawIdentifier
from app.core.logging import logger
from app.ingestion.parsers.base import BaseLegalParser
from app.models.legal_unit import LegalUnit


# ---------------------------------------------------------------------------
# Regex patterns (compiled once at module level for performance)
# ---------------------------------------------------------------------------

# Gazette / boilerplate lines to SKIP
_BOILERPLATE_PATTERNS = [
    re.compile(r"THE GAZETTE OF INDIA", re.IGNORECASE),
    re.compile(r"PART\s+II", re.IGNORECASE),
    re.compile(r"Registered No\.", re.IGNORECASE),
    re.compile(r"EXTRAORDINARY", re.IGNORECASE),
    re.compile(r"^\s*\d{1,4}\s*$"),                    # standalone page numbers
    re.compile(r"ACT NO\.\s+\d+\s+OF\s+\d{4}", re.IGNORECASE),
    re.compile(r"New Delhi,?\s+\w+day"),                # date headers
    re.compile(r"Saka,?\s+\d{4}"),                      # Indian calendar dates
    re.compile(r"Ministry of Electronics", re.IGNORECASE),
    re.compile(r"MeitY", re.IGNORECASE),
    re.compile(r"^\s*[—\-]{3,}\s*$"),                   # horizontal rules
    re.compile(r"^\s*\[\s*PART II"),                     # section header labels
    re.compile(r"jftLVªh la-", re.IGNORECASE),           # Hindi gazette header
    re.compile(r"Hkkjr\s+ljdkj", re.IGNORECASE),        # Hindi header
    re.compile(r"vlk/kj.k", re.IGNORECASE),             # Hindi extraordinary
]

# Chapter: "CHAPTER I", "CHAPTER II", "CHAPTER I — PRELIMINARY"
_CHAPTER_RE = re.compile(
    r"^\s*CHAPTER\s+([IVXLCDM]+)\s*(?:[—\-]\s*(.+))?$",
    re.IGNORECASE,
)
# Chapter title on its own next line (ALL CAPS, no number prefix)
_CHAPTER_TITLE_RE = re.compile(r"^\s*([A-Z][A-Z\s,]+[A-Z])\s*$")

# Section start: "1.", "2.", "22A." etc. (with optional alphabetic prefix/marginal notes)
_SECTION_RE = re.compile(r"^\s*(?:([A-Za-z\s,()–\-]{1,40}?)\s+)?(\d+[A-Z]?)\.\s+(.*)")

# Sub-section: "(1)" "(2)"
_SUBSECTION_RE = re.compile(r"^\s*\((\d+)\)\s+(.*)")

# Clause: "(a)" "(b)" … "(z)" but NOT "(1)" "(2)"
_CLAUSE_RE = re.compile(r"^\s*\(([a-z])\)\s+(.*)")

# Sub-clause: "(i)" "(ii)" "(iii)" "(iv)" "(v)"
_SUBCLAUSE_RE = re.compile(r"^\s*\((i{1,3}|iv|v{1,3}|vi{1,3}|ix|x{1,3})\)\s+(.*)", re.IGNORECASE)

# Long title / preamble
_PREAMBLE_RE = re.compile(r"^\s*An Act to", re.IGNORECASE)

# Definition line inside Section 2: "  (a) "data" means..."
_DEFINITION_TERM_RE = re.compile(r'"([^"]+)"\s+means', re.IGNORECASE)


class IndiaCodeDpdpParser(BaseLegalParser):
    """Parses the DPDP Act 2023 PDF (MeitY gazette) into LegalUnit objects.

    Extraction strategy:
      1. pdfplumber extracts raw text page-by-page.
      2. Each page is split into lines; boilerplate lines are stripped.
      3. A state machine walks the lines:
         - Detects Chapter boundaries → updates current_chapter.
         - Detects Section boundaries → flushes the previous section, starts a new one.
         - All sub-section / clause / sub-clause / proviso lines are appended to the
           current section's accumulated text.
      4. On section flush, a LegalUnit is created.
    """

    def source_label(self) -> str:
        return "meity-gazette"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def parse(
        self,
        file_path: Path,
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Parse the DPDP Act PDF into LegalUnit objects.

        Args:
            file_path: Path to the locally cached PDF.
            url: MeitY source URL (stored on every LegalUnit for citation).
            law: Must be LawIdentifier.DPDP.

        Returns:
            List of LegalUnit objects (one per section + preamble if present).

        Raises:
            FileNotFoundError: If file_path does not exist.
            ImportError: If pdfplumber is not installed.
            ValueError: If parsing yields zero legal units.
        """
        try:
            import pdfplumber  # noqa: PLC0415 — lazy import to keep base parsers clean
        except ImportError as exc:
            raise ImportError(
                "pdfplumber is required to parse PDF files. "
                "Install it with: pip install pdfplumber"
            ) from exc

        if not file_path.exists():
            raise FileNotFoundError(f"DPDP PDF not found: {file_path}")

        logger.info(f"[DpdpParser] Opening PDF: {file_path}")

        raw_lines: List[str] = []
        with pdfplumber.open(str(file_path)) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"[DpdpParser] PDF has {total_pages} pages.")
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                raw_lines.extend(text.splitlines())

        logger.info(f"[DpdpParser] Extracted {len(raw_lines)} raw lines.")

        clean_lines = self._clean_lines(raw_lines)
        logger.info(f"[DpdpParser] {len(clean_lines)} lines after boilerplate removal.")

        units = self._state_machine(clean_lines, url, law)

        if not units:
            raise ValueError(
                "[DpdpParser] Parsed zero legal units. "
                "Check that the PDF layout matches the expected gazette format."
            )

        logger.info(f"[DpdpParser] Extracted {len(units)} legal units.")
        return units

    # ------------------------------------------------------------------
    # Private: cleaning
    # ------------------------------------------------------------------

    def _is_boilerplate(self, line: str) -> bool:
        """Returns True if the line should be discarded as boilerplate."""
        stripped = line.strip()
        if not stripped:
            return True
        for pattern in _BOILERPLATE_PATTERNS:
            if pattern.search(stripped):
                return True
        return False

    def _clean_lines(self, raw_lines: List[str]) -> List[str]:
        """Strips boilerplate and normalises whitespace."""
        cleaned: List[str] = []
        for line in raw_lines:
            if self._is_boilerplate(line):
                continue
            # Normalise multiple spaces → single space (but keep leading indent)
            leading = len(line) - len(line.lstrip())
            normalised = " " * min(leading, 4) + " ".join(line.split())
            if normalised.strip():
                cleaned.append(normalised)
        return cleaned

    # ------------------------------------------------------------------
    # Private: state machine
    # ------------------------------------------------------------------

    def _state_machine(
        self,
        lines: List[str],
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Walks cleaned lines and emits LegalUnit objects."""

        units: List[LegalUnit] = []
        law_prefix = law.value  # "dpdp"

        # State
        current_chapter: str = "Preliminary"
        pending_chapter_title: bool = False     # True = next non-blank ALL-CAPS line is chapter title
        current_section_num: Optional[str] = None
        current_section_title: str = ""
        current_section_lines: List[str] = []
        in_preamble = False
        preamble_lines: List[str] = []

        def flush_section() -> None:
            nonlocal current_section_num, current_section_title, current_section_lines
            if current_section_num is None:
                return
            body = "\n".join(current_section_lines).strip()
            if not body:
                current_section_num = None
                current_section_title = ""
                current_section_lines = []
                return

            full_text = (
                f"{current_section_title}\n{body}" if current_section_title else body
            )
            unit_id = f"{law_prefix}:sec{current_section_num}"
            units.append(
                LegalUnit(
                    id=unit_id,
                    law="DPDP",
                    chapter=current_chapter,
                    article=f"Section {current_section_num}",
                    title=current_section_title or f"Section {current_section_num}",
                    text=full_text,
                    source=self.source_label(),
                    url=url,
                )
            )
            current_section_num = None
            current_section_title = ""
            current_section_lines = []

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # --- Long title / preamble ---
            if _PREAMBLE_RE.match(line):
                in_preamble = True
                preamble_lines = [line]
                continue

            # --- Chapter detection ---
            if m := _CHAPTER_RE.match(line):
                flush_section()
                in_preamble = False
                roman = m.group(1).upper()
                inline_title = (m.group(2) or "").strip()
                if inline_title:
                    current_chapter = f"Chapter {roman} — {inline_title}"
                    pending_chapter_title = False
                else:
                    current_chapter = f"Chapter {roman}"
                    pending_chapter_title = True  # expect title on next real line
                continue

            # --- Chapter title (line after bare "CHAPTER X") ---
            if pending_chapter_title:
                if _CHAPTER_TITLE_RE.match(line) and not _SECTION_RE.match(line):
                    current_chapter = f"{current_chapter} — {line.strip()}"
                    pending_chapter_title = False
                    continue
                else:
                    # It wasn't a title; the chapter stays as-is
                    pending_chapter_title = False
                    # Fall through and process this line normally

            # --- Section detection ---
            if m := _SECTION_RE.match(line):
                flush_section()
                in_preamble = False
                prefix = m.group(1).strip() if m.group(1) else ""
                current_section_num = m.group(2)
                rest = m.group(3).strip()
                title_body = rest.rstrip(".—").strip()
                if prefix:
                    current_section_title = f"{prefix} {title_body}".strip()
                else:
                    current_section_title = title_body
                if not current_section_title:
                    current_section_title = ""
                continue

            # --- Everything else: accumulate into current section ---
            if current_section_num is not None:
                # Annotate structural markers for human readability in the graph
                if _SUBSECTION_RE.match(line):
                    current_section_lines.append(line)
                elif _CLAUSE_RE.match(line):
                    current_section_lines.append(f"  {line}")
                elif _SUBCLAUSE_RE.match(line):
                    current_section_lines.append(f"    {line}")
                elif line.lower().startswith("provided that") or line.lower().startswith("provided further"):
                    current_section_lines.append(f"[Proviso] {line}")
                elif line.lower().startswith("explanation"):
                    current_section_lines.append(f"[Explanation] {line}")
                else:
                    current_section_lines.append(line)
                continue

            # --- Preamble / long title accumulation ---
            if in_preamble:
                preamble_lines.append(line)

        # Flush last section
        flush_section()

        # Emit preamble as a special unit if we have one
        if preamble_lines:
            preamble_text = " ".join(preamble_lines).strip()
            if preamble_text:
                units.insert(
                    0,
                    LegalUnit(
                        id=f"{law_prefix}:preamble",
                        law="DPDP",
                        chapter="Preamble",
                        article="Preamble",
                        title="Long Title",
                        text=preamble_text,
                        source=self.source_label(),
                        url=url,
                    ),
                )

        return units
