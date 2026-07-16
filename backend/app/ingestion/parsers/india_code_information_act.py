"""PDF parser for India's IT (Intermediary Guidelines and Digital Media Ethics Code) Rules, 2021.

Updated to handle amendments up to 10.02.2026 (including Synthetically Generated Information 
and Online Gaming Self-Regulatory frameworks).
Tool: pdfplumber
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from app.core.constants import LawIdentifier
from app.core.logging import logger
from app.ingestion.parsers.base import BaseLegalParser
from app.models.legal_unit import LegalUnit

# ---------------------------------------------------------------------------
# Regex patterns for IT Intermediary Rules, 2021
# ---------------------------------------------------------------------------

# Page headers, running titles, standalone page numbers, and separator artifacts
_HEADER_FOOTER_PATTERNS = [
    re.compile(r"^THE\s+INFORMATION\s+TECHNOLOGY\s+\(INTERMEDIARY\s+GUIDELINES", re.IGNORECASE),
    re.compile(r"^AND\s+DIGITAL\s+MEDIA\s+ETHICS\s+CODE\)\s+RULES,\s+2021", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),  # Standalone page numbers
    re.compile(r"^---\s*PAGE\s+\d+\s*---$", re.IGNORECASE),  # Text dump page separators
]

# Gazette footnote lines at bottom of pages (e.g., "Subs. by G.S.R. 120(E)...", "2 Ins. by G.S.R. 275(E)...")
_FOOTNOTE_LINE_RE = re.compile(
    r"^\s*(?:\$\{\}\^\{\d+\}|\d+\s*|\*\s*)?(?:(?:Subs\.|Ins\.|Omitted|Added|Renumbered|Vide|w\.e\.f\.).*|.*G\.S\.R\.\s*\d+|by\s+G\.S\.R\.|.*Pt\.\s+II,\s+Sec\.)",
    re.IGNORECASE,
)

# Structural hierarchy headings
_PART_RE = re.compile(r"^\s*PART\s+([IVXLCDM]+)\s*(?:[—\-–]\s*(.+))?$", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"^\s*CHAPTER\s+([IVXLCDM\d]+)\s*(?:[—\-–]\s*(.+))?$", re.IGNORECASE)
_APPENDIX_SCHEDULE_RE = re.compile(r"^\s*(APPENDIX|SCHEDULE)\s*(?:[—\-–]\s*(.+))?$", re.IGNORECASE)

# Standalone heading titles that appear on the line immediately following a Part/Chapter/Schedule
_STANDALONE_TITLE_RE = re.compile(r"^\s*([A-Z][A-Z\s,–\-—\(\)]+[A-Z\)])\s*$")

# Rules: e.g., "1. Short Title...", "3A. Appeal to Grievance...", "3. (1) Due diligence..."
# Handles leading footnote brackets like 1[3A. or ${}^{2}[(ca)$
_RULE_RE = re.compile(r"^\s*(?:\d+\[|\$\{\}\^\{\d+\}\s*\[?)*(?:\*\s*)?(\d+[A-Z]*)\.\s+(.*)")

# Sub-structures tailored for the Intermediary Rules:
# - Sub-rules: (1), (1A), (1B), (11), (12)
# - Clauses: (a), (z), (ca), (wa), (qa), (qb) [Crucial for Rule 2 definitions & Rule 3 due diligence]
# - Sub-clauses: (i), (iv), (ix), and uppercase Roman (I), (II), (III), (IV) [Used in Rule 3(1)(ca)(ii)]
_SUBRULE_RE = re.compile(r"^\s*(?:\d+\[|\$\{\}\^\{\d+\}\s*\[?)*\(([0-9]+[A-Z]*)\)\s+(.*)")
_CLAUSE_RE = re.compile(r"^\s*(?:\d+\[|\$\{\}\^\{\d+\}\s*\[?)*\(([a-z]+)\)\s+(.*)")
_SUBCLAUSE_RE = re.compile(r"^\s*(?:\d+\[|\$\{\}\^\{\d+\}\s*\[?)*\(((?:i|v|x)+|(?:I|V|X)+)\)\s+(.*)")


class ItIntermediaryRules2021Parser(BaseLegalParser):
    """Parses the IT (Intermediary Guidelines and Digital Media Ethics Code) Rules, 2021 PDF."""

    def source_label(self) -> str:
        return "india-code-it-rules-2021"

    def parse(
        self,
        file_path: Path,
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Parse the IT Intermediary Rules PDF into LegalUnit objects.

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
            raise FileNotFoundError(f"IT Rules PDF not found: {file_path}")

        logger.info(f"[ItRulesParser] Opening PDF: {file_path}")

        raw_lines: List[str] = []
        with pdfplumber.open(str(file_path)) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"[ItRulesParser] PDF has {total_pages} pages.")

            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                raw_lines.extend(text.splitlines())

        logger.info(f"[ItRulesParser] Extracted {len(raw_lines)} raw lines.")
        clean_lines = self._clean_lines(raw_lines)
        logger.info(f"[ItRulesParser] {len(clean_lines)} lines remaining after noise filtering.")

        units = self._state_machine(clean_lines, url, law)

        if not units:
            raise ValueError("[ItRulesParser] Parsed zero legal units. Check PDF layout or regex rules.")

        logger.info(f"[ItRulesParser] Successfully extracted {len(units)} legal units.")
        return units

    # ------------------------------------------------------------------
    # Cleaning helpers
    # ------------------------------------------------------------------

    def _is_noise_or_footnote(self, line: str) -> bool:
        """Returns True if the line is running header/footer or bottom-of-page Gazette footnote."""
        stripped = line.strip()
        if not stripped:
            return True

        for pattern in _HEADER_FOOTER_PATTERNS:
            if pattern.match(stripped):
                return True

        if _FOOTNOTE_LINE_RE.match(stripped):
            return True

        return False

    def _clean_lines(self, raw_lines: List[str]) -> List[str]:
        """Filters out noise and normalizes whitespace while preserving indent context."""
        cleaned: List[str] = []
        for line in raw_lines:
            if self._is_noise_or_footnote(line):
                continue
            leading = len(line) - len(line.lstrip())
            normalized = " " * min(leading, 4) + " ".join(line.split())
            if normalized.strip():
                cleaned.append(normalized)
        return cleaned

    # ------------------------------------------------------------------
    # State machine & text processing
    # ------------------------------------------------------------------

    def _split_rule_title(self, rest: str) -> Tuple[str, str]:
        """Separates the rule title from the rule body content."""
        # Handle standard legal separators: .-, .—, . --, . -, or period before em-dash
        for sep in [".—", ".-", ". --", ". -", " — ", " – ", "\uFFFD"]:
            if sep in rest:
                parts = rest.split(sep, 1)
                return parts[0].strip().rstrip("."), parts[1].strip()

        # Handle formatting like Rule 3: "(1) Due diligence by an intermediary: An intermediary..."
        m_colon = re.search(r":\s+(?=[A-Z])", rest)
        if m_colon and ("Due diligence" in rest or "Grievance" in rest):
            idx = m_colon.start()
            title = rest[:idx].strip()
            title = re.sub(r"^\(\d+\)\s*", "", title)  # Strip leading (1) from title if present
            body = rest[idx + 1:].strip()
            return title, body

        # Fallback: First period followed by a sub-rule like (1) or capital letter
        m = re.search(r"\.\s+(?=\(\d+\)|[A-Z])", rest)
        if m:
            idx = m.start()
            title = rest[:idx].strip()
            body = rest[idx + 1:].strip()
            return title, body

        return rest, ""

    def _clean_content(self, text: str) -> str:
        """Cleans replacement characters, LaTeX/footnote markup, and trailing brackets."""
        text = text.replace("\uFFFD", '"')
        
        # Remove LaTeX style markers from OCR e.g., ${}^{2}[(ca)$ -> (ca)
        text = re.sub(r"\$\{\}\^\{\d+\}\s*\[?", "", text)
        text = re.sub(r"\$\{\}\^\{\d+\}", "", text)
        text = text.replace("$", "")

        # Recursively remove footnote brackets like 1[electronic signature] or 2[***]
        while re.search(r"\d+\[([^\]]*)\]", text):
            text = re.sub(r"\d+\[([^\]]*)\]", r"\1", text)
        
        # Remove unmatched opening footnote markers like "1[" or "2["
        text = re.sub(r"\b\d+\[", "", text)

        # Normalize horizontal whitespace while preserving line breaks
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        return "\n".join(lines).strip()

    def _state_machine(
        self,
        lines: List[str],
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Walks clean lines to assemble structural units (Parts, Rules, Schedules)."""
        units: List[LegalUnit] = []
        law_prefix = law.value  # e.g., "it_rules_2021"

        current_part: str = "Preliminary"
        current_chapter: Optional[str] = None
        pending_heading_title: bool = False

        current_rule_num: Optional[str] = None
        current_rule_title: str = ""
        current_rule_lines: List[str] = []

        def get_hierarchy_context() -> str:
            if current_chapter:
                return f"{current_part} | {current_chapter}"
            return current_part

        def flush_rule() -> None:
            nonlocal current_rule_num, current_rule_title, current_rule_lines
            if current_rule_num is None:
                return

            body_text = "\n".join(current_rule_lines).strip()
            body_text = self._clean_content(body_text)

            full_text = (
                f"{current_rule_title}\n{body_text}"
                if current_rule_title
                else body_text
            )

            # Distinguish between standard rules and Schedule/Appendix sections
            if "SCHEDULE" in current_part.upper() or "APPENDIX" in current_part.upper():
                unit_id = f"{law_prefix}:appx_{current_rule_num.lower()}"
                article_label = f"Item {current_rule_num}"
            else:
                unit_id = f"{law_prefix}:rule_{current_rule_num.lower()}"
                article_label = f"Rule {current_rule_num}"

            units.append(
                LegalUnit(
                    id=unit_id,
                    law="IT_INTERMEDIARY_RULES_2021",
                    chapter=get_hierarchy_context(),
                    article=article_label,
                    title=current_rule_title or article_label,
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

            # --- Detect Part Boundary ---
            if m := _PART_RE.match(line):
                flush_rule()
                roman = m.group(1).upper()
                inline_title = (m.group(2) or "").strip()
                current_part = f"Part {roman} - {inline_title}" if inline_title else f"Part {roman}"
                current_chapter = None  # Reset chapter when entering a new Part
                pending_heading_title = not bool(inline_title)
                continue

            # --- Detect Chapter Boundary (Found inside Part III) ---
            if m := _CHAPTER_RE.match(line):
                flush_rule()
                c_num = m.group(1).upper()
                inline_title = (m.group(2) or "").strip()
                current_chapter = f"Chapter {c_num} - {inline_title}" if inline_title else f"Chapter {c_num}"
                pending_heading_title = not bool(inline_title)
                continue

            # --- Detect Appendix / Schedule Boundary ---
            if m := _APPENDIX_SCHEDULE_RE.match(line):
                flush_rule()
                name = m.group(1).upper()
                inline_title = (m.group(2) or "").strip()
                current_part = f"{name} - {inline_title}" if inline_title else name
                current_chapter = None
                pending_heading_title = not bool(inline_title)
                continue

            # --- Detect Standalone Heading Title on subsequent line ---
            if pending_heading_title:
                if _STANDALONE_TITLE_RE.match(line) and not _RULE_RE.match(line):
                    if current_chapter and current_chapter.endswith("Chapter " + current_chapter.split()[-1]):
                        current_chapter = f"{current_chapter} - {line}"
                    else:
                        current_part = f"{current_part} - {line}"
                    pending_heading_title = False
                    continue
                pending_heading_title = False

            # --- Detect Rule / Appendix Item Boundary ---
            if m := _RULE_RE.match(line):
                potential_rule = m.group(1)
                
                # Prevent matching numbered lists inside an active rule body unless it's alphanumeric (e.g., 3A, 4B)
                if current_rule_num is not None and potential_rule.isdigit():
                    if int(potential_rule) != int(re.sub(r"\D", "", current_rule_num or "0")) + 1:
                        # Treat as sub-item content within the current rule
                        current_rule_lines.append(line)
                        continue

                flush_rule()
                current_rule_num = potential_rule
                rest = m.group(2).strip()

                title, body = self._split_rule_title(rest)
                current_rule_title = self._clean_content(title)
                current_rule_lines = [body] if body else []
                continue

            # --- Accumulate content into current Rule ---
            if current_rule_num is not None:
                # Apply structural indentations for scannability
                if _SUBRULE_RE.match(line):
                    current_rule_lines.append(f"\n{line}")
                elif _CLAUSE_RE.match(line):
                    current_rule_lines.append(f"  {line}")
                elif _SUBCLAUSE_RE.match(line):
                    current_rule_lines.append(f"    {line}")
                else:
                    current_rule_lines.append(line)
                continue

        # Flush the final rule or schedule unit
        flush_rule()

        return units