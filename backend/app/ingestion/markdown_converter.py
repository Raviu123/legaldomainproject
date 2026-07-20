"""Document to Markdown converter utility.

Converts raw statutory files (PDF, HTML, TXT) into normalized Markdown text
preserving section headers and removing running headers, footers, and page numbers.
"""

import re
from pathlib import Path
from typing import List

from app.core.logging import logger

# Common gazette boilerplate patterns to drop
_BOILERPLATE_PATTERNS = [
    re.compile(r"THE GAZETTE OF INDIA", re.IGNORECASE),
    re.compile(r"PART\s+II", re.IGNORECASE),
    re.compile(r"Registered No\.", re.IGNORECASE),
    re.compile(r"EXTRAORDINARY", re.IGNORECASE),
    re.compile(r"^\s*\d{1,4}\s*$"),  # Page numbers
    re.compile(r"ACT NO\.\s+\d+\s+OF\s+\d{4}", re.IGNORECASE),
    re.compile(r"New Delhi,?\s+\w+day", re.IGNORECASE),
    re.compile(r"Saka,?\s+\d{4}", re.IGNORECASE),
    re.compile(r"^\s*[—\-]{3,}\s*$"),
]

# Section / Chapter headers
_CHAPTER_HEADER_RE = re.compile(
    r"^\s*(CHAPTER|PART|TITLE)\s+([IVXLCDM\d]+)\b(.*)",
    re.IGNORECASE,
)
_SECTION_HEADER_RE = re.compile(
    r"^\s*(\d+[A-Z]?)\.\s+(.*)",
    re.IGNORECASE,
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
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                for line in text.splitlines():
                    cleaned = line.strip()
                    if cleaned and not _is_boilerplate(cleaned):
                        lines.append(_format_markdown_line(cleaned))
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
                        lines.append(_format_markdown_line(cleaned))
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
    """Checks if a line is gazette headers/footers or page numbers."""
    for pattern in _BOILERPLATE_PATTERNS:
        if pattern.search(line):
            return True
    return False


def _format_markdown_line(line: str) -> str:
    """Annotates section headers with Markdown # or ##."""
    if _CHAPTER_HEADER_RE.match(line):
        return f"# {line}"
    elif _SECTION_HEADER_RE.match(line):
        return f"## {line}"
    return line
