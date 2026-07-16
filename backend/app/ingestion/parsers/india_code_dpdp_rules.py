"""PDF parser for India's Digital Personal Data Protection Rules, 2025.

Source : https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf
Format : PDF
Tool   : pdfplumber
"""

import re
from pathlib import Path
from typing import List, Optional

from app.core.constants import LawIdentifier
from app.core.logging import logger
from app.ingestion.parsers.base import BaseLegalParser
from app.models.legal_unit import LegalUnit

# ---------------------------------------------------------------------------
# Regex patterns and keywords
# ---------------------------------------------------------------------------

_BOILERPLATE_KEYWORDS = [
    "Subs. by",
    "Ins. by",
    "w.e.f.",
    "ibid.",
    "vide notification",
    "Gazette of India",
    "Ministry of Electronics",
]

_BOILERPLATE_PATTERNS = [
    re.compile(r"^THE GAZETTE OF INDIA", re.IGNORECASE),
    re.compile(r"^EXTRAORDINARY", re.IGNORECASE),
    re.compile(r"^PART\s+II", re.IGNORECASE),
    re.compile(r"^NOTIFICATION", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),  # page numbers
    re.compile(r"^\s*[—\-]{3,}\s*$"),  # horizontal rules
]

# Chapter: e.g. "CHAPTER I", "CHAPTER II - CONSENT"
_CHAPTER_RE = re.compile(
    r"^\s*CHAPTER\s+([IVXLCDM\d]+)\s*(?:[—\-–]\s*(.+))?$",
    re.IGNORECASE,
)
_CHAPTER_TITLE_RE = re.compile(r"^\s*([A-Z][A-Z\s,]+[A-Z])\s*$")

# Rule: e.g. "1. Short title...", "2. Definitions...", "10. Consent..."
_RULE_RE = re.compile(r"^\s*(?:\d+\[)?(\d+[A-Z]?)\.\s+(.*)")

# Sub-structures inside rule body
_SUBSECTION_RE = re.compile(r"^\s*\((\d+)\)\s+(.*)")
_CLAUSE_RE = re.compile(r"^\s*\(([a-z])\)\s+(.*)")
_SUBCLAUSE_RE = re.compile(r"^\s*\((i{1,3}|iv|v{1,3}|vi{1,3}|ix|x{1,3})\)\s+(.*)", re.IGNORECASE)


class IndiaCodeDpdpRulesParser(BaseLegalParser):
    """Parses the DPDP Rules 2025 PDF into LegalUnit objects."""

    def source_label(self) -> str:
        return "meity-rules"

    def parse(
        self,
        file_path: Path,
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Parse the DPDP Rules PDF into LegalUnit objects.

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
            raise FileNotFoundError(f"DPDP Rules PDF not found: {file_path}")

        logger.info(f"[DpdpRulesParser] Opening PDF: {file_path}")

        raw_lines: List[str] = []
        with pdfplumber.open(str(file_path)) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"[DpdpRulesParser] PDF has {total_pages} pages.")

            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                raw_lines.extend(text.splitlines())

        logger.info(f"[DpdpRulesParser] Extracted {len(raw_lines)} raw lines.")

        clean_lines = self._clean_lines(raw_lines)
        logger.info(f"[DpdpRulesParser] {len(clean_lines)} lines remaining after boilerplate removal.")

        units = self._state_machine(clean_lines, url, law)

        if not units:
            raise ValueError("[DpdpRulesParser] Parsed zero legal units. Check layout or skip limits.")

        logger.info(f"[DpdpRulesParser] Successfully extracted {len(units)} legal units.")
        return units

    # ------------------------------------------------------------------
    # Cleaning helpers
    # ------------------------------------------------------------------

    def _is_boilerplate(self, line: str) -> bool:
        """Returns True if the line matches footnote or page-header boilerplate."""
        stripped = line.strip()
        if not stripped:
            return True
        for kw in _BOILERPLATE_KEYWORDS:
            if kw in stripped:
                return True
        for pattern in _BOILERPLATE_PATTERNS:
            if pattern.match(stripped):
                return True
        return False

    def _clean_lines(self, raw_lines: List[str]) -> List[str]:
        """Filters out boilerplate and normalizes whitespace."""
        cleaned: List[str] = []
        for line in raw_lines:
            if self._is_boilerplate(line):
                continue
            # Normalize whitespace while keeping indentation context
            leading = len(line) - len(line.lstrip())
            normalized = " " * min(leading, 4) + " ".join(line.split())
            if normalized.strip():
                cleaned.append(normalized)
        return cleaned

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _split_rule_title(self, rest: str) -> tuple[str, str]:
        """Separates the rule title from the rule body content.

        Indian Act/Rules sections usually start as "1. Title. - (1) Body...".
        """
        # Split on common delimiters including em-dash/long-dash and replacement char \uFFFD
        for sep in ["\uFFFD", ".—", " — ", " – ", " - "]:
            if sep in rest:
                parts = rest.split(sep, 1)
                return parts[0].strip().rstrip("."), parts[1].strip()

        # Fallback: first period followed by a subsection (1) or a capital letter
        m = re.search(r"\.\s*(\(\d+\)|[A-Z])", rest)
        if m:
            idx = m.start()
            title = rest[:idx].strip()
            body = rest[idx + 1:].strip()
            return title, body

        return rest, ""

    def _clean_content(self, text: str) -> str:
        """Cleans quotes, footnote indicators, and duplicate spaces from text."""
        # Replace the PDF reader's replacement char for smart quotes with standard double quotes
        text = text.replace("\uFFFD", '"')
        text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        # Clean footnote brackets like 1[electronic signature] -> electronic signature
        text = re.sub(r"\d+\[([^\]]+)\]", r"\1", text)
        # Normalize horizontal spaces but preserve newlines
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        return "\n".join(lines).strip()

    def _state_machine(
        self,
        lines: List[str],
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Walks clean lines to assemble preamble, chapters, and rules."""
        units: List[LegalUnit] = []
        law_prefix = law.value  # "dpdp_rules"

        current_chapter: str = "Preliminary"
        pending_chapter_title: bool = False
        current_rule_num: Optional[str] = None
        current_rule_title: str = ""
        current_rule_lines: List[str] = []

        in_preamble = False
        preamble_lines: List[str] = []

        # Find where notification starts (preamble)
        parsing_started = False

        def flush_rule() -> None:
            nonlocal current_rule_num, current_rule_title, current_rule_lines
            if current_rule_num is None:
                return

            body_text = "\n".join(current_rule_lines).strip()
            body_text = self._clean_content(body_text)

            # Reconstruct text block
            full_text = (
                f"{current_rule_title}\n{body_text}"
                if current_rule_title
                else body_text
            )

            unit_id = f"{law_prefix}:rule{current_rule_num.lower()}"
            units.append(
                LegalUnit(
                    id=unit_id,
                    law="DPDP_RULES",
                    chapter=current_chapter,
                    article=f"Rule {current_rule_num}",
                    title=current_rule_title or f"Rule {current_rule_num}",
                    text=full_text,
                    source=self.source_label(),
                    url=url,
                )
            )

            current_rule_num = None
            current_rule_title = ""
            current_rule_lines = []

        for line_raw in lines:
            line = line_raw.strip()
            if not line:
                continue

            # Start parsing when we see notification-like preamble keywords
            if not parsing_started:
                if "exercise of the powers" in line.lower() or "whereas the draft" in line.lower() or "chapter" in line.lower() or "rule" in line.lower():
                    parsing_started = True
                    in_preamble = True
            
            if not parsing_started:
                continue

            # --- Detect Chapter boundary ---
            if m := _CHAPTER_RE.match(line):
                flush_rule()
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
                if _CHAPTER_TITLE_RE.match(line) and not _RULE_RE.match(line):
                    current_chapter = f"{current_chapter} - {line}"
                    pending_chapter_title = False
                    continue
                pending_chapter_title = False

            # --- Detect Rule boundary ---
            if m := _RULE_RE.match(line):
                flush_rule()
                in_preamble = False
                current_rule_num = m.group(1)
                rest = m.group(2).strip()

                title, body = self._split_rule_title(rest)
                current_rule_title = self._clean_content(title)
                current_rule_lines = [body] if body else []
                continue

            # --- Accumulate content into current Rule ---
            if current_rule_num is not None:
                if _SUBSECTION_RE.match(line):
                    current_rule_lines.append(line)
                elif _CLAUSE_RE.match(line):
                    current_rule_lines.append(f"  {line}")
                elif _SUBCLAUSE_RE.match(line):
                    current_rule_lines.append(f"    {line}")
                else:
                    current_rule_lines.append(line)
                continue

            # --- Accumulate content into Preamble ---
            if in_preamble:
                preamble_lines.append(line_raw)

        # Flush the final rule
        flush_rule()

        # Emit preamble as the first LegalUnit if found
        if preamble_lines:
            preamble_text = " ".join(preamble_lines).strip()
            preamble_text = self._clean_content(preamble_text)
            if preamble_text:
                units.insert(
                    0,
                    LegalUnit(
                        id=f"{law_prefix}:preamble",
                        law="DPDP_RULES",
                        chapter="Preamble",
                        article="Preamble",
                        title="Notification Preamble",
                        text=preamble_text,
                        source=self.source_label(),
                        url=url,
                    ),
                )

        return units
