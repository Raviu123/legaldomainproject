"""LLM Orchestrator.

Implements Step 7 (LLM answer generation) from context.md.
Loads the versioned prompt template, formats the retrieved context,
calls the configured LLM (NVIDIA/OpenAI-compatible), validates the JSON
response against a Pydantic model, and retries once on validation failure.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.logging import logger

# Path to versioned prompt template
_PROMPT_PATH = Path(__file__).parent / "prompts" / "ask_v1.txt"


class LlmAnswer(BaseModel):
    """Validated Pydantic model for the LLM JSON response."""

    answer: str = Field(..., min_length=10)
    confidence: float = Field(..., ge=0.0, le=1.0)
    related_laws: List[str] = Field(default_factory=list)


def _load_prompt_template() -> str:
    """Loads the versioned ask prompt template from disk."""
    if not _PROMPT_PATH.exists():
        raise FileNotFoundError(f"Prompt template not found: {_PROMPT_PATH}")
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_context_string(results: List[Dict[str, Any]]) -> str:
    """Formats retrieval results into a structured context string for the prompt."""
    parts = []
    for idx, rec in enumerate(results, start=1):
        law = rec.get("law") or "Unknown Law"
        article = rec.get("article") or rec.get("id") or "Unknown Article"
        title = rec.get("title") or ""
        text = rec.get("text") or ""
        url = rec.get("url") or ""
        sources = ", ".join(rec.get("retrieval_sources") or [rec.get("retrieval_source", "")])

        header = f"[{idx}] {article}"
        if title:
            header += f" — {title}"
        header += f" ({law})"
        if url:
            header += f"\n    URL: {url}"
        header += f"\n    Retrieved via: {sources}"

        parts.append(f"{header}\n\n{text}")

    return "\n\n---\n\n".join(parts)


def _strip_json_fences(raw: str) -> str:
    """Strips markdown code fences from an LLM response, if present."""
    raw = raw.strip()
    # Remove ```json ... ``` or ``` ... ```
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _call_llm(prompt: str) -> str:
    """Calls the configured LLM and returns the raw text response."""
    client_args: Dict[str, Any] = {"api_key": settings.OPENAI_API_KEY}
    if settings.OPENAI_BASE_URL:
        client_args["base_url"] = settings.OPENAI_BASE_URL

    model = settings.OPENAI_MODEL or settings.LLM_MODEL or "gpt-4o-mini"
    client = OpenAI(**client_args)

    logger.info(f"[Orchestrator] Calling LLM: model={model}, prompt_length={len(prompt)} chars.")

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,  # Low temperature for factual legal responses
        max_tokens=1500,
    )
    choice = response.choices[0].message
    # Handle reasoning models where content may come back empty
    content = choice.content or getattr(choice, "reasoning_content", None) or ""
    logger.info(f"[Orchestrator] LLM response received ({len(content)} chars).")
    return content.strip()


def _parse_and_validate(raw: str) -> LlmAnswer:
    """Strips fences, parses JSON, and validates against LlmAnswer Pydantic model."""
    cleaned = _strip_json_fences(raw)
    data = json.loads(cleaned)
    return LlmAnswer(**data)


def generate_answer(
    question: str,
    retrieved_results: List[Dict[str, Any]],
) -> Optional[LlmAnswer]:
    """Full orchestration: format context → prompt → call LLM → validate → retry once.

    Args:
        question: The user's legal question.
        retrieved_results: Merged, ranked retrieval results from all three legs.

    Returns:
        Validated LlmAnswer Pydantic model, or None if LLM is not configured.

    Raises:
        RuntimeError: If both the initial call and the retry fail validation.
    """
    if not settings.OPENAI_API_KEY:
        logger.warning("[Orchestrator] OPENAI_API_KEY not set. Skipping LLM generation.")
        return None

    template = _load_prompt_template()
    context_str = _build_context_string(retrieved_results)
    prompt = template.format(question=question, context=context_str)

    # First attempt
    try:
        raw = _call_llm(prompt)
        return _parse_and_validate(raw)
    except (json.JSONDecodeError, ValidationError, KeyError) as first_err:
        logger.warning(
            f"[Orchestrator] First LLM response failed validation: {first_err}. Retrying..."
        )

    # Single retry with corrective instruction (per agents.md §6)
    retry_prompt = (
        prompt
        + "\n\nYour previous response was not valid JSON matching the required schema. "
        "Respond ONLY with the raw JSON object, no markdown, no fences, no preamble."
    )
    try:
        raw = _call_llm(retry_prompt)
        return _parse_and_validate(raw)
    except (json.JSONDecodeError, ValidationError, KeyError) as retry_err:
        logger.error(f"[Orchestrator] Retry also failed: {retry_err}. Raising.")
        raise RuntimeError(
            f"LLM returned invalid output after 2 attempts. Last error: {retry_err}"
        ) from retry_err
