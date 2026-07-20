"""Universal AI-Powered Legal Document Parser.

Converts any statutory legal document (PDF, HTML, TXT) into normalized LegalUnit objects
using LLM-driven structured extraction and Markdown boundary analysis.
"""

import json
import re
from pathlib import Path
from typing import List, Optional

from pydantic import ValidationError

from app.core.config import settings
from app.core.constants import LAW_REGISTRY, LawIdentifier
from app.core.logging import logger
from app.ingestion.markdown_converter import convert_to_markdown
from app.ingestion.parsers.base import BaseLegalParser
from app.models.legal_unit import DefinitionModel, LegalUnit
from app.models.universal_schema import ExtractedDocumentPayload, ExtractedLegalUnit


class UniversalAiParser(BaseLegalParser):
    """Universal AI Legal Parser capable of ingesting any PDF or HTML statutory document.

    Flow:
      1. Converts source document into clean Markdown via `markdown_converter`.
      2. Breaks Markdown into structural chunks (Chapters/Sections).
      3. Uses LLM structured extraction (JSON mode) to extract section numbers, titles,
         chapters, body text, defined terms, and cross-references.
      4. Fallbacks to structural Markdown regex state-machine if LLM is offline.
      5. Emits standard `List[LegalUnit]` objects ready for Neo4j and Qdrant.
    """

    def source_label(self) -> str:
        return "universal-ai-parser"

    def parse(
        self,
        file_path: Path,
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Parse raw file into normalized LegalUnit objects."""
        if not file_path.exists():
            raise FileNotFoundError(f"Source document file not found: {file_path}")

        logger.info(f"[UniversalAiParser] Converting document to Markdown: {file_path.name}")
        markdown_text = convert_to_markdown(file_path)

        if not markdown_text.strip():
            raise ValueError(f"[UniversalAiParser] Converted document is empty: {file_path.name}")

        # Attempt AI LLM Extraction first
        units: List[LegalUnit] = []
        if settings.OPENAI_API_KEY:
            try:
                logger.info(f"[UniversalAiParser] Running LLM Structured Extraction on {file_path.name}...")
                units = self._extract_via_llm(markdown_text, url, law)
            except Exception as exc:
                logger.warning(f"[UniversalAiParser] LLM extraction failed ({exc}), falling back to Heading Regex Parser.")
                units = []

        # Fallback to intelligent Markdown Heading State-Machine Parser if LLM is skipped/failed
        if not units:
            logger.info(f"[UniversalAiParser] Processing via Heading Structural Parser...")
            units = self._extract_via_heading_parser(markdown_text, url, law)

        if not units:
            raise ValueError(f"[UniversalAiParser] Failed to extract any legal units from {file_path.name}")

        logger.info(f"[UniversalAiParser] Successfully parsed {len(units)} legal units for law '{law.value}'.")
        return units

    # ------------------------------------------------------------------
    # LLM Structured Extraction Strategy
    # ------------------------------------------------------------------

    def _extract_via_llm(
        self,
        markdown_text: str,
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Sends markdown chunks to LLM to extract structured legal units."""
        from openai import OpenAI

        client_args = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            client_args["base_url"] = settings.OPENAI_BASE_URL

        model = settings.OPENAI_MODEL or settings.LLM_MODEL or "gpt-4o-mini"
        client = OpenAI(**client_args)

        chunks = self._chunk_markdown(markdown_text, max_chars=4000)
        logger.info(f"[UniversalAiParser] Split document into {len(chunks)} LLM chunks.")

        law_prefix = law.value
        all_units: List[LegalUnit] = []

        for idx, chunk in enumerate(chunks, start=1):
            logger.info(f"[UniversalAiParser] Prompting LLM chunk {idx}/{len(chunks)}...")
            prompt = self._build_extraction_prompt(chunk, law.value)

            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a legal document parsing AI. Output pure valid JSON matching the requested schema."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"} if "gpt-" in model or "claude" in model else None,
                )
                raw_json = response.choices[0].message.content or "{}"
                extracted_units = self._parse_json_response(raw_json)

                for item in extracted_units:
                    sec_clean = re.sub(r"[^\w]", "", item.article_or_section.lower()) or f"unit{len(all_units) + 1}"
                    unit_id = f"{law_prefix}:{sec_clean}"

                    defs = [DefinitionModel(term=t, definition=item.body_text[:200]) for t in item.defined_terms]
                    all_units.append(
                        LegalUnit(
                            id=unit_id,
                            law=law.value.upper(),
                            chapter=item.chapter or "General Provisions",
                            article=item.article_or_section,
                            section=item.article_or_section,
                            title=item.title or item.article_or_section,
                            text=item.body_text,
                            source=self.source_label(),
                            url=url,
                            definitions=defs,
                            references=item.cross_references,
                        )
                    )
            except Exception as err:
                logger.warning(f"[UniversalAiParser] Error parsing chunk {idx}: {err}")
                continue

        return all_units

    def _build_extraction_prompt(self, markdown_chunk: str, law_name: str) -> str:
        """Constructs prompt for LLM structured extraction."""
        return f"""Analyze the following statutory legal text from '{law_name.upper()}'.
Extract all legal sections, articles, or recitals into a JSON object.

JSON Schema format:
{{
  "units": [
    {{
      "chapter": "Chapter name or Title header (e.g. Chapter I — Preliminary)",
      "article_or_section": "Article 6 or Section 12",
      "title": "Header title of section",
      "body_text": "Complete verbatim text of section",
      "defined_terms": ["term1", "term2"],
      "cross_references": ["Article 4", "Section 10"]
    }}
  ]
}}

Document Text:
---
{markdown_chunk}
---
Return ONLY valid JSON matching the schema above."""

    def _parse_json_response(self, raw_json: str) -> List[ExtractedLegalUnit]:
        """Strips fences and parses ExtractedDocumentPayload."""
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_json.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)
        if "units" in data:
            payload = ExtractedDocumentPayload(**data)
            return payload.units
        elif isinstance(data, list):
            return [ExtractedLegalUnit(**item) for item in data]
        return []

    # ------------------------------------------------------------------
    # Markdown Heading Structural Fallback Strategy
    # ------------------------------------------------------------------

    def _extract_via_heading_parser(
        self,
        markdown_text: str,
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """State machine parsing Markdown `#` and `##` headings into LegalUnits."""
        units: List[LegalUnit] = []
        law_prefix = law.value

        current_chapter = "General Provisions"
        current_section_num: Optional[str] = None
        current_section_title: str = ""
        current_lines: List[str] = []

        section_regex = re.compile(
            r"^(?:##|#)?\s*(?:(Section|Article|Recital|Rule)\s+)?(\d+[A-Z]?|Recital\s+\d+)\.?\s*(.*)",
            re.IGNORECASE,
        )
        chapter_regex = re.compile(
            r"^(?:#)\s*(CHAPTER|PART|TITLE)\s+([IVXLCDM\d]+)\s*(?:[—\-–]\s*(.+))?",
            re.IGNORECASE,
        )

        def flush():
            nonlocal current_section_num, current_section_title, current_lines
            if current_section_num is None:
                return
            body = "\n".join(current_lines).strip()
            if not body:
                return

            sec_id_clean = re.sub(r"[^\w]", "", current_section_num.lower())
            unit_id = f"{law_prefix}:sec{sec_id_clean}"

            units.append(
                LegalUnit(
                    id=unit_id,
                    law=law.value.upper(),
                    chapter=current_chapter,
                    article=f"Section {current_section_num}",
                    section=f"Section {current_section_num}",
                    title=current_section_title or f"Section {current_section_num}",
                    text=f"{current_section_title}\n{body}" if current_section_title else body,
                    source=self.source_label(),
                    url=url,
                )
            )
            current_section_num = None
            current_section_title = ""
            current_lines = []

        lines = markdown_text.splitlines()
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check chapter boundary
            if m := chapter_regex.match(stripped):
                flush()
                chap_type = m.group(1).capitalize()
                chap_num = m.group(2).upper()
                chap_title = (m.group(3) or "").strip()
                current_chapter = f"{chap_type} {chap_num}" + (f" — {chap_title}" if chap_title else "")
                continue

            # Check section boundary
            if m := section_regex.match(stripped):
                flush()
                prefix = m.group(1) or "Section"
                sec_num = m.group(2)
                title = m.group(3) or ""
                current_section_num = f"{prefix} {sec_num}".strip()
                current_section_title = title.strip()
                continue

            # Accumulate body text
            if current_section_num is not None:
                current_lines.append(stripped)
            else:
                # Initial preamble or unsectioned header
                if not current_section_num:
                    current_section_num = "1"
                    current_section_title = "Preamble / General Provisions"
                    current_lines.append(stripped)

        flush()
        return units

    def _chunk_markdown(self, text: str, max_chars: int = 4000) -> List[str]:
        """Splits markdown text into logical chunks under max_chars length."""
        paragraphs = text.split("\n\n")
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_len = 0

        for para in paragraphs:
            if current_len + len(para) > max_chars and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_len = len(para)
            else:
                current_chunk.append(para)
                current_len += len(para)

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks
