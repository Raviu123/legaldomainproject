"""Universal Legal Document Parser with Hybrid Extraction Strategy.

Converts any statutory legal document (PDF, HTML, TXT) into normalized LegalUnit objects.
Uses regex-based parsing first (fast, free), with LLM fallback for complex/unusual documents.
"""

import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from collections import defaultdict

from pydantic import ValidationError

from app.core.config import settings
from app.core.constants import LAW_REGISTRY, LawIdentifier
from app.core.logging import logger
from app.ingestion.markdown_converter import convert_to_markdown
from app.ingestion.parsers.base import BaseLegalParser
from app.models.legal_unit import DefinitionModel, LegalUnit
from app.models.universal_schema import ExtractedDocumentPayload, ExtractedLegalUnit


class UniversalAiParser(BaseLegalParser):
    """Hybrid Legal Parser: Regex first, LLM fallback for complex cases."""

    # Quality threshold for regex extraction (0.0 - 1.0)
    REGEX_QUALITY_THRESHOLD = 0.5  # Lowered to be more permissive
    
    # Laws where regex is known to work well - skip LLM entirely
    FORCE_REGEX_LAWS = ['sg_pdpa', 'pdpa_sg', 'it_act', 'pdp_sg', 'singapore_pdpa']

    def source_label(self) -> str:
        return "universal-hybrid-parser"

    def parse(
        self,
        file_path: Path,
        url: str,
        law: LawIdentifier,
    ) -> List[LegalUnit]:
        """Parse raw file into normalized LegalUnit objects."""
        if not file_path.exists():
            raise FileNotFoundError(f"Source document file not found: {file_path}")

        logger.info(f"[UniversalParser] Converting document to Markdown: {file_path.name}")
        markdown_text = convert_to_markdown(file_path)

        if not markdown_text.strip():
            raise ValueError(f"[UniversalParser] Converted document is empty: {file_path.name}")

        # Save converted markdown for inspection
        try:
            md_path = settings.markdown_data_dir / f"{file_path.stem}.md"
            md_path.write_text(markdown_text, encoding="utf-8")
            logger.info(f"[UniversalParser] Saved markdown to: {md_path}")
        except Exception as e:
            logger.warning(f"[UniversalParser] Could not save markdown: {e}")

        # ================================================================
        # Check if we should force regex for this law
        # ================================================================
        force_regex = any(law_value in str(law.value).lower() for law_value in self.FORCE_REGEX_LAWS)
        
        if force_regex:
            logger.info(f"[UniversalParser] 🔒 Forcing regex for {law.value}")
            regex_units, quality_score = self._parse_with_regex(markdown_text, url, law)
            if regex_units and len(regex_units) > 10:
                logger.info(f"[UniversalParser] ✅ Regex extracted {len(regex_units)} units (skipping LLM)")
                return regex_units

        # ================================================================
        # Try Regex Parser FIRST
        # ================================================================
        logger.info(f"[UniversalParser] Attempting regex-based parsing...")
        regex_units, quality_score = self._parse_with_regex(markdown_text, url, law)
        
        # ================================================================
        # Validate Regex Quality
        # ================================================================
        if regex_units and len(regex_units) > 10:
            logger.info(f"[UniversalParser] Regex extracted {len(regex_units)} units (quality: {quality_score:.2f})")
            
            if quality_score >= self.REGEX_QUALITY_THRESHOLD or len(regex_units) > 50:
                logger.info(f"[UniversalParser] ✅ Using regex results")
                return regex_units
            else:
                logger.warning(f"[UniversalParser] Quality below threshold ({quality_score:.2f} < {self.REGEX_QUALITY_THRESHOLD})")
        
        # ================================================================
        # Fallback to LLM
        # ================================================================
        if settings.OPENAI_API_KEY:
            logger.info(f"[UniversalParser] 🤖 Falling back to LLM extraction...")
            try:
                llm_units = self._extract_via_llm(markdown_text, url, law)
                if llm_units:
                    logger.info(f"[UniversalParser] ✅ LLM extracted {len(llm_units)} units")
                    return llm_units
            except Exception as exc:
                logger.warning(f"[UniversalParser] LLM extraction failed: {exc}")
        
        # ================================================================
        # Return what regex got (better than nothing)
        # ================================================================
        if regex_units:
            logger.warning(f"[UniversalParser] Using fallback regex results ({len(regex_units)} units)")
            return regex_units
        
        raise ValueError(f"[UniversalParser] Failed to extract any legal units from {file_path.name}")

    # ===================================================================
    # REGEX-BASED PARSER (NO LLM CALLS)
    # ===================================================================
    
    def _parse_with_regex(
        self,
        markdown_text: str,
        url: str,
        law: LawIdentifier,
    ) -> Tuple[List[LegalUnit], float]:
        """State-machine parser. Universal: works for GDPR, DPDP, PDPA, Privacy Act, etc."""
        units: List[LegalUnit] = []
        law_prefix = law.value

        # ── State ────────────────────────────────────────────────────────
        current_chapter = "General Provisions"
        current_section_num: Optional[str] = None
        current_section_title: str = ""
        current_lines: List[str] = []
        current_refs: List[str] = []
        sections_extracted = 0

        # ── Patterns ──────────────────────────────────────────────────────
        # NOTE: The markdown converter (markdown_converter.py) prefixes
        # section/part/schedule header lines with Markdown heading markers
        # ("#", "##", or "###"). These patterns MUST tolerate 0-3 leading
        # '#' characters (with optional whitespace) or they will silently
        # fail to match, causing regex extraction to under-count sections
        # and trigger an unnecessary (slow, costly) LLM fallback.

        # P1: Explicit keyword — "Section 12A", "Sec 5", "Article 3", "Recital 3"
        EXPLICIT_SEC = re.compile(
            r"^#{0,3}\s*(?:Section|Sec\.?|Art(?:icle)?|Recital)\s+(\d+[A-Z]?)\b\.?\s*(.*)",
            re.IGNORECASE,
        )

        # P2: Dash-only format — "2.—(1) Interpretation", "12A.– Short title"
        DASH_SEC = re.compile(
            r"^#{0,3}\s*(\d+[A-Z]?)\s*\.\s*[\u2014\u2013\-]\s*(?:\(\d+\)\s*)?(.*)",
        )

        # P3: Number-only with dot — "2. Interpretation" (FALLBACK)
        NUMBER_DOT_SEC = re.compile(
            r"^#{0,3}\s*(\d+[A-Z]?)\s*\.\s+(.*)",
        )

        # Part/Chapter/Division headers
        PART_HDR = re.compile(
            r"^#{0,3}\s*(?:PART|CHAPTER|TITLE|DIVISION)\s+([IVXLCDM\d]+)\b\s*(?:[\u2014\u2013\-]\s*(.*))?",
            re.IGNORECASE,
        )

        # Schedule headers
        SCHEDULE_HDR = re.compile(
            r"^#{0,3}\s*(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH)\s+SCHEDULE\b",
            re.IGNORECASE,
        )

        # Cross-references
        XREF = re.compile(
            r"(?:section|subsection|article|clause)\s+(\d+[A-Z]?(?:\s*\([^)]*\))?)",
            re.IGNORECASE,
        )

        # ── Quality estimate ───────────────────────────────────────────────
        # Count unique section markers in raw text
        total_expected = len(set(
            re.findall(
                r"(?:(?:Section|Sec\.?|Art(?:icle)?)\s+\d+[A-Z]?|\b\d+[A-Z]?\s*\.\s*[\u2014\u2013\-]|\b\d+[A-Z]?\s*\.\s+[A-Z])",
                markdown_text,
                re.IGNORECASE,
            )
        ))
        if total_expected == 0:
            total_expected = max(1, len(re.findall(r"^#+\s+\S", markdown_text, re.MULTILINE)))

        # ── Definition extractor ──────────────────────────────────────────
        def extract_definitions(body: str) -> List[DefinitionModel]:
            """Extract all definitions from section body."""
            flat = re.sub(r"\s*\n\s*", " ", body)
            DEFN = re.compile(
                r'[\u201c\u201e\u2018\"\']((?:[^\u201d\u201c\u201e\n\"]{1,80}))[\u201d\u2019\"\']'
                r'\s+(?:means|includes)\s+'
                r'((?:(?![\u201c\u201e\u2018\"\']\S{1,80}[\u201d\u2019\"\']\s+(?:means|includes))[^;]){5,})'
                r'(?:;|\Z)',
                re.IGNORECASE,
            )
            seen = set()
            defs = []
            for m in DEFN.finditer(flat):
                term = m.group(1).strip()
                defn = re.sub(r"\s+", " ", m.group(2)).strip().rstrip(";,")
                if len(term) > 1 and len(defn) > 5 and term.lower() not in seen:
                    seen.add(term.lower())
                    defs.append(DefinitionModel(term=term, definition=defn[:600]))
            return defs

        # ── Flush helper ───────────────────────────────────────────────────
        def flush() -> None:
            nonlocal current_section_num, current_section_title
            nonlocal current_lines, current_refs, sections_extracted

            if current_section_num is None or not current_lines:
                return
            body = "\n".join(current_lines).strip()
            if not body:
                return

            # Extract definitions
            defs = extract_definitions(body)
            refs = list(dict.fromkeys(current_refs))

            sec_id = re.sub(r"[^\w]", "", current_section_num.lower())
            title = current_section_title or current_section_num
            full_text = f"{title}\n{body}" if current_section_title else body

            units.append(LegalUnit(
                id=f"{law_prefix}:sec{sec_id}",
                law=law.value.upper(),
                chapter=current_chapter,
                article=current_section_num,
                section=current_section_num,
                title=title,
                text=full_text,
                source=self.source_label(),
                url=url,
                definitions=defs,
                references=refs,
            ))
            sections_extracted += 1

            current_section_num = None
            current_section_title = ""
            current_lines = []
            current_refs = []

        # ── Main parsing loop ──────────────────────────────────────────────
        lines = self._clean_markdown_lines(markdown_text.splitlines())
        
        for line in lines:
            s = line.strip()
            if not s:
                continue

            # Schedule header
            if m := SCHEDULE_HDR.match(s):
                flush()
                current_chapter = f"{m.group(1).title()} Schedule"
                continue

            # Part/Chapter header
            if m := PART_HDR.match(s):
                flush()
                part_num = m.group(1)
                part_title = (m.group(2) or "").strip()
                current_chapter = f"Part {part_num}" + (f" — {part_title}" if part_title else "")
                continue

            # Explicit keyword section (highest priority)
            if m := EXPLICIT_SEC.match(s):
                flush()
                current_section_num = m.group(1)
                current_section_title = m.group(2).strip().rstrip(".")
                continue

            # Dash-only format (Commonwealth / Singapore style)
            if m := DASH_SEC.match(s):
                flush()
                current_section_num = m.group(1)
                current_section_title = m.group(2).strip().rstrip(".")
                continue

            # Number-only with dot (Fallback for US/India style)
            if m := NUMBER_DOT_SEC.match(s):
                # Check if it looks like a section (has title after number)
                title = m.group(2).strip()
                if len(title) > 3 and not re.match(r'^[a-z]', title):
                    flush()
                    current_section_num = m.group(1)
                    current_section_title = title.rstrip(".")
                    continue

            # Accumulate into current section body
            if current_section_num is not None:
                for ref in XREF.findall(s):
                    current_refs.append(ref)
                current_lines.append(s)

        flush()

        # ── Quality score ─────────────────────────────────────────────────
        if total_expected > 0:
            quality_score = min(sections_extracted / total_expected, 1.0)
        elif units:
            quality_score = 0.7
        else:
            quality_score = 0.0

        return units, quality_score

    def _clean_markdown_lines(self, lines: List[str]) -> List[str]:
        """Clean markdown lines before parsing."""
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # Remove page numbers
            if re.match(r'^\s*\d{1,4}\s*$', stripped):
                continue
            
            # Remove boilerplate
            if self._is_boilerplate(stripped):
                continue
            
            # Remove excessive whitespace
            stripped = re.sub(r'\s+', ' ', stripped)
            cleaned.append(stripped)
        
        return cleaned

    def _is_boilerplate(self, line: str) -> bool:
        """Check if line is boilerplate text."""
        patterns = [
            r'^THE GAZETTE OF INDIA',
            r'^PART\s+II',
            r'^Registered No\.',
            r'^EXTRAORDINARY',
            r'^ACT NO\.\s+\d+\s+OF\s+\d{4}',
            r'^New Delhi,?\s+\w+day',
            r'^Saka,?\s+\d{4}',
            r'^\s*[—\-]{3,}\s*$',
            r'^THE STATUTES OF THE REPUBLIC OF SINGAPORE',
            r'^Personal Data Protection Act',
            r'^2020 REVISED EDITION',
            r'^Prepared and Published by',
            r'^Informal Consolidation',
        ]
        
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False

    # ===================================================================
    # LLM EXTRACTION STRATEGY (Fallback)
    # ===================================================================

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
        logger.info(f"[UniversalParser] Split document into {len(chunks)} LLM chunks.")

        law_prefix = law.value
        all_units: List[LegalUnit] = []

        for idx, chunk in enumerate(chunks, start=1):
            logger.info(f"[UniversalParser] Processing chunk {idx}/{len(chunks)} with LLM...")
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

                    defs = []
                    for t in item.defined_terms:
                        def_text = self._extract_definition_from_text(item.body_text, t)
                        defs.append(DefinitionModel(term=t, definition=def_text[:500] if def_text else item.body_text[:200]))

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
                logger.warning(f"[UniversalParser] Error parsing chunk {idx}: {err}")
                continue

        return all_units

    def _extract_definition_from_text(self, text: str, term: str) -> str:
        """Extract definition for a term from text."""
        pattern = rf'[“"](?:{re.escape(term)})[“"]\s+means\s+([^;]+(?:;|$))'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        pattern = rf'[“"](?:{re.escape(term)})[“"]\s+includes\s+([^;]+(?:;|$))'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return ""

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