"""Document to Markdown converter utility.

Converts raw statutory files (PDF, HTML, TXT) into normalized Markdown text
preserving section headers and removing running headers, footers, and page numbers.
"""

import re
from pathlib import Path
from typing import List, Tuple

from app.core.logging import logger

# Boilerplate patterns (expanded for multiple jurisdictions)
_BOILERPLATE_PATTERNS = [
    # India-specific
    re.compile(r"THE GAZETTE OF INDIA", re.IGNORECASE),
    re.compile(r"PART\s+II", re.IGNORECASE),
    re.compile(r"Registered No\.", re.IGNORECASE),
    re.compile(r"EXTRAORDINARY", re.IGNORECASE),
    re.compile(r"ACT NO\.\s+\d+\s+OF\s+\d{4}", re.IGNORECASE),
    re.compile(r"New Delhi,?\s+\w+day", re.IGNORECASE),
    re.compile(r"Saka,?\s+\d{4}", re.IGNORECASE),
    # Singapore-specific (PDPA)
    re.compile(r"THE STATUTES OF THE REPUBLIC OF SINGAPORE", re.IGNORECASE),
    re.compile(r"Personal Data Protection Act", re.IGNORECASE),
    re.compile(r"REVISED EDITION", re.IGNORECASE),
    re.compile(r"Prepared and Published by", re.IGNORECASE),
    re.compile(r"Informal Consolidation", re.IGNORECASE),
    re.compile(r"LAW REVISION COMMISSION", re.IGNORECASE),
    # Generic
    re.compile(r"^\s*\d{1,4}\s*$"),  # Page numbers
    re.compile(r"^\s*[—\-]{3,}\s*$"),  # Horizontal lines
    re.compile(r"^TABLE OF CONTENTS", re.IGNORECASE),
    re.compile(r"^ARRANGEMENT OF SECTIONS", re.IGNORECASE),
    re.compile(r"^CONTENTS", re.IGNORECASE),
]

# Pattern to detect when a line might be a section header
_SECTION_HEADER_PATTERN = re.compile(
    r'^(?:#\s*)?(?:Section|Sec\.?|Art(?:icle)?|Recital)\s+\d+[A-Z]?|^\d+[A-Z]?\s*[.—\-–]',
    re.IGNORECASE
)


def convert_to_markdown(file_path: Path) -> str:
    """Converts a PDF, HTML, or text file into clean Markdown text."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found for Markdown conversion: {file_path}")

    ext = file_path.suffix.lower()

    if ext == ".pdf":
        return _convert_pdf_to_markdown(file_path)
    elif ext in [".html", ".htm"]:
        return _convert_html_to_markdown(file_path)
    else:
        return _convert_txt_to_markdown(file_path)


def _convert_pdf_to_markdown(file_path: Path) -> str:
    """Extracts text from PDF and formats into Markdown structure."""
    lines: List[str] = []

    try:
        import pdfplumber

        logger.info(f"[MarkdownConverter] Converting PDF via pdfplumber: {file_path.name}")
        with pdfplumber.open(str(file_path)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                for line in text.splitlines():
                    cleaned = line.strip()
                    if cleaned and not _is_boilerplate(cleaned):
                        # Format the line with proper Markdown
                        formatted = _format_markdown_line(cleaned)
                        lines.append(formatted)
    except Exception as exc:
        logger.warning(f"[MarkdownConverter] pdfplumber failed ({exc}), falling back to pypdf...")
        try:
            import pypdf

            reader = pypdf.PdfReader(str(file_path))
            for page in reader.pages:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    cleaned = line.strip()
                    if cleaned and not _is_boilerplate(cleaned):
                        formatted = _format_markdown_line(cleaned)
                        lines.append(formatted)
        except Exception as inner_exc:
            logger.error(f"[MarkdownConverter] Failed to parse PDF: {inner_exc}")
            raise inner_exc

    return "\n\n".join(lines)


def _convert_html_to_markdown(file_path: Path) -> str:
    """Converts HTML DOM structure into Markdown headings and paragraphs."""
    try:
        from bs4 import BeautifulSoup

        logger.info(f"[MarkdownConverter] Converting HTML: {file_path.name}")
        raw_html = file_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(raw_html, "html.parser")

        # Strip unneeded elements
        for element in soup(["script", "style", "header", "footer", "nav"]):
            element.decompose()

        lines: List[str] = []
        for elem in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "li"]):
            text = " ".join(elem.get_text().split())
            if not text or _is_boilerplate(text):
                continue

            tag = elem.name.lower()
            if tag in ["h1", "h2"]:
                lines.append(f"# {text}")
            elif tag in ["h3", "h4"]:
                lines.append(f"## {text}")
            elif tag in ["h5", "h6"]:
                lines.append(f"### {text}")
            else:
                lines.append(_format_markdown_line(text))

        return "\n\n".join(lines)
    except Exception as exc:
        logger.error(f"[MarkdownConverter] HTML conversion failed: {exc}")
        return file_path.read_text(encoding="utf-8", errors="ignore")


def _convert_txt_to_markdown(file_path: Path) -> str:
    """Reads raw text or markdown file directly."""
    raw = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = [
        _format_markdown_line(line.strip())
        for line in raw.splitlines()
        if line.strip() and not _is_boilerplate(line.strip())
    ]
    return "\n\n".join(lines)


def _is_boilerplate(line: str) -> bool:
    """Checks if a line is boilerplate text."""
    # If it looks like a section header, it's NOT boilerplate
    if _SECTION_HEADER_PATTERN.search(line):
        return False
    
    # Check against boilerplate patterns
    for pattern in _BOILERPLATE_PATTERNS:
        if pattern.search(line):
            return True
    return False


def _format_markdown_line(line: str) -> str:
    """Annotates section headers with Markdown # or ##."""
    # Check for Part/Chapter/Title headers (highest level)
    if re.match(r'^\s*(?:CHAPTER|PART|TITLE|BOOK)\s+', line, re.IGNORECASE):
        return f"# {line}"
    
    # Check for Section/Article headers with explicit keyword
    if re.match(r'^\s*(?:Section|Sec\.?|Art(?:icle)?|Recital)\s+', line, re.IGNORECASE):
        return f"## {line}"
    
    # Check for number-only sections (e.g., "2. Interpretation", "2.—(1) In this Act")
    if re.match(r'^\s*\d+[A-Z]?\s*[.—\-–]', line):
        return f"## {line}"
    
    # Keep definition lines as-is (they'll be handled by parser)
    if re.match(r'^[“"\'‘]', line):
        return line
    
    # Keep list items/ subsections as-is
    if re.match(r'^\([a-zA-Z0-9]\)', line):
        return line
    
    # All other text
    return line


def debug_markdown_conversion(file_path: Path) -> None:
    """Debug the Markdown conversion output."""
    print(f"\n{'='*60}")
    print(f"DEBUG: Converting {file_path.name}")
    print(f"{'='*60}")
    
    markdown = convert_to_markdown(file_path)
    
    # Find Section 2 specifically
    lines = markdown.split('\n')
    section_2_start = -1
    section_2_end = -1
    
    for i, line in enumerate(lines):
        if 'Section 2' in line or '2.—' in line or '2. ' in line:
            if section_2_start == -1:
                section_2_start = i
            # Look for next section
            if i > section_2_start and re.match(r'##\s*Section\s+3|##\s*3\.', line):
                section_2_end = i
                break
    
    if section_2_start >= 0:
        if section_2_end == -1:
            section_2_end = min(section_2_start + 50, len(lines))
        
        print(f"\nSection 2 found at line {section_2_start}")
        print(f"{'='*60}")
        for i in range(section_2_start, min(section_2_end, len(lines))):
            print(f"{i:4d}: {lines[i]}")
        print(f"{'='*60}")
    else:
        print("❌ Section 2 NOT found in Markdown!")
        
        # Show first 30 lines to debug
        print("\nFirst 30 lines of Markdown:")
        print(f"{'='*60}")
        for i, line in enumerate(lines[:30]):
            print(f"{i:4d}: {line}")
        print(f"{'='*60}") 