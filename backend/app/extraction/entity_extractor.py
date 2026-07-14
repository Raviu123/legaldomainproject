"""Entity and Concept Extractor.

Extracts semantic concepts from legal texts using a hybrid approach:
deterministic regex keyword matches (0 cost, fast) and LLM-based custom extraction
with local file caching (optional, accurate).
"""

import json
import re
from typing import Dict, List

from app.core.config import settings
from app.core.logging import logger

# Path for caching LLM concept extractions (uses settings.cache_dir for consistent path resolution)
CACHE_FILE_PATH = settings.cache_dir / "concept_cache.json"

# Compile regex patterns for core legal concepts
# Matches are case-insensitive and boundaries (\b) are checked to prevent substring mismatches
CORE_CONCEPTS_PATTERNS: Dict[str, List[re.Pattern]] = {
    "Consent": [re.compile(r"\bconsent\b", re.IGNORECASE)],
    "Personal Data": [
        re.compile(r"\bpersonal data\b", re.IGNORECASE),
        re.compile(r"\bdata concerning\b", re.IGNORECASE),
    ],
    "Controller": [re.compile(r"\bcontroller\b", re.IGNORECASE)],
    "Processor": [re.compile(r"\bprocessor\b", re.IGNORECASE)],
    "Data Subject": [re.compile(r"\bdata subject\b", re.IGNORECASE)],
    "Profiling": [re.compile(r"\bprofiling\b", re.IGNORECASE)],
    "Pseudonymisation": [
        re.compile(r"\bpseudonymisation\b", re.IGNORECASE),
        re.compile(r"\bpseudonymised\b", re.IGNORECASE),
    ],
    "Special Categories of Data": [
        re.compile(r"\bspecial categories of personal data\b", re.IGNORECASE),
        re.compile(r"\bracial or ethnic origin\b", re.IGNORECASE),
        re.compile(r"\bpolitical opinions\b", re.IGNORECASE),
        re.compile(r"\breligious or philosophical beliefs\b", re.IGNORECASE),
        re.compile(r"\btrade union membership\b", re.IGNORECASE),
    ],
    "Biometric Data": [
        re.compile(r"\bbiometric data\b", re.IGNORECASE),
        re.compile(r"\bbiometric\b", re.IGNORECASE),
    ],
    "Genetic Data": [re.compile(r"\bgenetic data\b", re.IGNORECASE)],
    "Health Data": [
        re.compile(r"\bdata concerning health\b", re.IGNORECASE),
        re.compile(r"\bhealth data\b", re.IGNORECASE),
    ],
    "Security": [
        re.compile(r"\bsecurity of processing\b", re.IGNORECASE),
        re.compile(r"\btechnical and organisational measures\b", re.IGNORECASE),
    ],
    "Data Breach": [
        re.compile(r"\bpersonal data breach\b", re.IGNORECASE),
        re.compile(r"\bsecurity incident\b", re.IGNORECASE),
    ],
    "Supervisory Authority": [
        re.compile(r"\bsupervisory authority\b", re.IGNORECASE),
        re.compile(r"\bcommissioner\b", re.IGNORECASE),
    ],
    "Cross-border Transfer": [
        re.compile(r"\btransfer of personal data to a third country\b", re.IGNORECASE),
        re.compile(r"\bthird country\b", re.IGNORECASE),
        re.compile(r"\binternational organisation\b", re.IGNORECASE),
    ],
    "Right to Erasure": [
        re.compile(r"\bright to erasure\b", re.IGNORECASE),
        re.compile(r"\bright to be forgotten\b", re.IGNORECASE),
    ],
    "Right of Access": [re.compile(r"\bright of access\b", re.IGNORECASE)],
    "Right to Rectification": [re.compile(r"\bright to rectification\b", re.IGNORECASE)],
    "Data Portability": [
        re.compile(r"\bright to data portability\b", re.IGNORECASE),
        re.compile(r"\bdata portability\b", re.IGNORECASE),
    ],
    "Right to Object": [re.compile(r"\bright to object\b", re.IGNORECASE)],
    "Legitimate Interest": [
        re.compile(r"\blegitimate interest\b", re.IGNORECASE),
        re.compile(r"\blegitimate interests\b", re.IGNORECASE),
    ],
    "Data Protection Officer": [
        re.compile(r"\bdata protection officer\b", re.IGNORECASE),
        re.compile(r"\bdpo\b", re.IGNORECASE),
    ],
    "Data Protection Impact Assessment": [
        re.compile(r"\bdata protection impact assessment\b", re.IGNORECASE),
        re.compile(r"\bdpia\b", re.IGNORECASE),
    ],
    "Penalty": [
        re.compile(r"\badministrative fines\b", re.IGNORECASE),
        re.compile(r"\bpenalties\b", re.IGNORECASE),
        re.compile(r"\bfine\b", re.IGNORECASE),
    ],
    "Exception": [
        re.compile(r"\bderogations\b", re.IGNORECASE),
        re.compile(r"\bderogation\b", re.IGNORECASE),
        re.compile(r"\bexception\b", re.IGNORECASE),
    ],
    "Child Data": [
        re.compile(r"\bchild\b", re.IGNORECASE),
        re.compile(r"\bchildren\b", re.IGNORECASE),
    ],
}


def load_concept_cache() -> Dict[str, List[str]]:
    """Loads cache of LLM extracted concepts from disk."""
    if not CACHE_FILE_PATH.exists():
        return {}
    try:
        with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load concept cache: {e}")
        return {}


def save_concept_cache(cache: Dict[str, List[str]]) -> None:
    """Saves cache of LLM extracted concepts to disk."""
    try:
        CACHE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save concept cache: {e}")


def extract_concepts_heuristically(text: str) -> List[str]:
    """Extracts concepts from text based on regex pattern matching (fast, 0 cost)."""
    concepts = []
    for concept, patterns in CORE_CONCEPTS_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(text):
                concepts.append(concept)
                break
    return concepts


# Global flag to dynamically disable LLM queries if authentication fails
LLM_DISABLED = False


def extract_concepts_via_llm(text: str, unit_id: str) -> List[str]:
    """Queries OpenAI or Anthropic LLM to extract custom nuanced concepts (slow, cost).

    Uses local cache to avoid redundant API calls.
    """
    global LLM_DISABLED
    if LLM_DISABLED or not settings.ENABLE_LLM_CONCEPT_EXTRACTION:
        return []

    cache = load_concept_cache()
    if unit_id in cache:
        return cache[unit_id]

    # Check if we have API keys configured
    api_key_set = any(
        [settings.ANTHROPIC_API_KEY, settings.OPENAI_API_KEY, settings.GEMINI_API_KEY]
    )
    if not api_key_set:
        # Fall back silently to empty if no LLM config is active
        return []

    logger.info(f"Querying LLM for custom concepts extraction on: {unit_id}")

    prompt = (
        "You are a legal expert. Extract 3 to 7 primary legal concepts or topics "
        "discussed in this legal article text.\n"
        "Respond ONLY with a JSON list of strings, with no markdown formatting or extra text.\n\n"
        f'Text:\n"{text}"\n'
    )

    concepts: List[str] = []

    try:
        if settings.OPENAI_API_KEY:
            from openai import OpenAI

            client_args = {"api_key": settings.OPENAI_API_KEY}
            if settings.OPENAI_BASE_URL:
                client_args["base_url"] = settings.OPENAI_BASE_URL

            client = OpenAI(**client_args)
            model = settings.OPENAI_MODEL or settings.LLM_MODEL or "gpt-4o-mini"

            response = client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}], temperature=0.0
            )
            raw_response = response.choices[0].message.content.strip()
            # Clean possible markdown fences
            if raw_response.startswith("```"):
                raw_response = raw_response.split("json")[-1].split("```")[0].strip()
            concepts = json.loads(raw_response)

        elif settings.ANTHROPIC_API_KEY:
            from anthropic import Anthropic

            client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

            response = client.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=1000,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_response = response.content[0].text.strip()
            if raw_response.startswith("```"):
                raw_response = raw_response.split("json")[-1].split("```")[0].strip()
            concepts = json.loads(raw_response)

        # Capitalize concepts for consistency
        concepts = [c.strip().title() for c in concepts if isinstance(c, str)]

        # Cache results
        cache[unit_id] = concepts
        save_concept_cache(cache)

    except Exception as e:
        err_msg = str(e)
        logger.error(f"Failed to extract concepts via LLM for {unit_id}: {e}")
        # Check for authentication or key errors to fail fast
        if (
            "401" in err_msg
            or "unauthorized" in err_msg.lower()
            or "api_key" in err_msg.lower()
            or "api key" in err_msg.lower()
        ):
            logger.warning(
                "Disabling LLM queries for the rest of this run due to API authentication failure."
            )
            LLM_DISABLED = True
        # Return empty list, falling back to heuristics
        concepts = []

    return concepts


def extract_concepts(text: str, unit_id: str) -> List[str]:
    """Hybrid concept extraction.

    Combines regex heuristics and LLM custom concepts, deduplicating them.
    """
    # 1. Run heuristics (instant, free)
    concepts = extract_concepts_heuristically(text)

    # 2. Run LLM (cached, fallback to empty if no key or failure)
    llm_concepts = extract_concepts_via_llm(text, unit_id)

    # Merge and deduplicate
    all_concepts = set(concepts + llm_concepts)
    return sorted(list(all_concepts))
