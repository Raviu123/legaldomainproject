"""Parser for Australia Privacy Act 1988.

Robust parser that extracts chapters, parts, and sections from crawled HTML.
"""

import re
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from app.core.constants import LawIdentifier
from app.models.legal_unit import LegalUnit
from app.ingestion.parsers.base import BaseLegalParser


class AustraliaPrivacyActParser(BaseLegalParser):
    """Parses Australia Privacy Act 1988 HTML documents into normalized LegalUnits."""

    def parse(
        self,
        file_path: Path,
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Parses the combined Crawl4AI output file into a list of LegalUnits.

        Args:
            file_path: Path to the cached crawled raw file.
            url: Seed URL of the law.
            law: The LawIdentifier enum.

        Returns:
            List[LegalUnit]: List of parsed legal units.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")

        raw_content = file_path.read_text(encoding="utf-8")
        units: List[LegalUnit] = []

        # If the file contains multiple crawled pages, process them,
        # but focus on extracting legal sections from each page.
        pages = raw_content.split("<!-- PAGE_URL:")
        for page_idx, page in enumerate(pages):
            clean_page = page.strip()
            if not clean_page:
                continue

            # Extract page URL
            lines = clean_page.split("\n")
            page_url = url
            if "-->" in lines[0]:
                page_url = lines[0].split("-->")[0].strip()
                html_body = "\n".join(lines[1:])
            else:
                html_body = clean_page

            # Parse HTML structure
            soup = BeautifulSoup(html_body, "html.parser")

            # Remove boilerplate elements (nav, footer, styles, scripts)
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            # Fallback to text-based regex extraction if the DOM classes aren't uniform
            page_text = soup.get_text("\n")

            # Pre-parse Parts and Divisions to maintain hierarchy
            # Part matching, e.g., "Part I—Preliminary" or "Part II—Privacy Commissioner"
            part_pattern = re.compile(
                r"^\s*(Part\s+[IVXLCD\d]+[A-Z]?)\s*[\u2014\u2013-]?\s*(.*)$",
                re.IGNORECASE | re.MULTILINE,
            )
            # Division matching, e.g., "Division 1—Introduction"
            div_pattern = re.compile(
                r"^\s*(Division\s+\d+[A-Z]?)\s*[\u2014\u2013-]?\s*(.*)$",
                re.IGNORECASE | re.MULTILINE,
            )

            # Find all sections using regex
            # Matches: "6  Interpretation" or "Section 6", "11A  APP entities" etc.
            # We look for section numbers followed by double spaces or tab/newline and a title.
            section_pattern = re.compile(
                r"^\s*(\d+[A-Z]?)\s{2,}(.+)$",
                re.MULTILINE,
            )

            # Let's run a line-by-line parser to build the hierarchy
            current_part = "Part I - Preliminary"
            current_division = ""

            section_blocks = []
            current_section_num = None
            current_section_title = None
            current_section_text: List[str] = []

            for line in page_text.split("\n"):
                line_stripped = line.strip()
                if not line_stripped:
                    continue

                # Check if this line is a Part header
                if m_part := part_pattern.match(line_stripped):
                    # Flush current section
                    if current_section_num:
                        section_blocks.append(
                            (
                                current_section_num,
                                current_section_title,
                                "\n".join(current_section_text),
                                current_part,
                                current_division,
                            )
                        )
                        current_section_num = None
                        current_section_text = []

                    part_num = m_part.group(1).strip()
                    part_title = m_part.group(2).strip()
                    current_part = f"{part_num} - {part_title}"
                    current_division = ""
                    continue

                # Check if this line is a Division header
                if m_div := div_pattern.match(line_stripped):
                    # Flush current section
                    if current_section_num:
                        section_blocks.append(
                            (
                                current_section_num,
                                current_section_title,
                                "\n".join(current_section_text),
                                current_part,
                                current_division,
                            )
                        )
                        current_section_num = None
                        current_section_text = []

                    div_num = m_div.group(1).strip()
                    div_title = m_div.group(2).strip()
                    current_division = f"{div_num} - {div_title}"
                    continue

                # Check if this line is a Section header
                if m_sec := section_pattern.match(line_stripped):
                    # Flush previous section
                    if current_section_num:
                        section_blocks.append(
                            (
                                current_section_num,
                                current_section_title,
                                "\n".join(current_section_text),
                                current_part,
                                current_division,
                            )
                        )

                    current_section_num = m_sec.group(1).strip()
                    current_section_title = m_sec.group(2).strip()
                    current_section_text = []
                    continue

                # Otherwise, it's text content under the current section
                if current_section_num:
                    current_section_text.append(line_stripped)

            # Flush the last section on the page
            if current_section_num:
                section_blocks.append(
                    (
                        current_section_num,
                        current_section_title,
                        "\n".join(current_section_text),
                        current_part,
                        current_division,
                    )
                )

            # If no sections were extracted (e.g. page was poorly formatted or too short),
            # fall back to creating a single section for the whole page.
            if not section_blocks:
                unit_id = f"{law.value}:section_main_{page_idx}"
                units.append(
                    LegalUnit(
                        id=unit_id,
                        law=law.value.upper(),
                        chapter="General",
                        article="Whole Document",
                        title="Privacy Act 1988",
                        text=page_text[:10000],
                        source="legislation.gov.au",
                        url=page_url,
                    )
                )
                continue

            # Convert extracted blocks into LegalUnits
            for sec_num, sec_title, sec_text, part, division in section_blocks:
                # Clean up multiple whitespaces
                cleaned_text = re.sub(r"\s+", " ", sec_text).strip()
                if not cleaned_text:
                    continue

                unit_id = f"{law.value}:sec{sec_num.lower()}"
                
                # Context / Chapter structure
                chapter_context = part
                if division:
                    chapter_context += f" | {division}"

                units.append(
                    LegalUnit(
                        id=unit_id,
                        law=law.value.upper(),
                        chapter=chapter_context,
                        article=f"Section {sec_num}",
                        title=sec_title,
                        text=cleaned_text,
                        source="legislation.gov.au",
                        url=page_url,
                    )
                )

        return units
