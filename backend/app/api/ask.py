"""Ask API endpoint — Hybrid Graph + Vector RAG.

Implements the /api/v1/ask endpoint described in context.md §7 and agents.md §9.
Pipeline:
  1. Vector search  — embed query, retrieve top-k similar chunks from Qdrant.
  2. Graph traversal — expand from vector hit IDs + any explicit article mentions
                       via REFERENCES / DEFINES / HAS_CONCEPT / HAS_EXCEPTION edges.
  3. Keyword search — supplementary Neo4j exact-match across Article/Recital nodes.
  4. Merge & rank   — deduplicate by node ID, apply source weights, top-12.
  5. LLM generation — cite-only prompt, JSON output validated against Pydantic model.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import logger
from app.rag.llm.orchestrator import generate_answer
from app.rag.retrieval.graph_search import graph_search_by_query
from app.rag.retrieval.keyword_search import keyword_search
from app.rag.retrieval.merger import merge_and_rank
from app.rag.retrieval.vector_search import vector_search

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    """Request model for the /ask endpoint."""

    question: str = Field(..., min_length=5, description="The legal question to answer.")
    law: Optional[str] = Field(
        default=None,
        description="Optional law name to scope retrieval (e.g. 'GDPR'). Leave null for cross-law search.",
    )
    top_k: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Number of top results to retrieve per search leg (default: 8).",
    )


class SourceModel(BaseModel):
    """A single cited source returned in the answer."""

    id: str = Field(..., description="Node ID in Neo4j (e.g. 'gdpr:art6').")
    article: Optional[str] = Field(None, description="Article/section identifier.")
    title: Optional[str] = Field(None, description="Title of the legal unit.")
    law: str = Field(..., description="Law name (e.g. 'GDPR').")
    url: str = Field(..., description="Source URL for the legal text.")
    retrieval_sources: List[str] = Field(
        default_factory=list,
        description="Which retrieval legs found this node (vector/graph/keyword).",
    )
    score: float = Field(..., description="Final merged relevance score.")


class AskResponse(BaseModel):
    """Response model for the /ask endpoint."""

    answer: str = Field(..., description="LLM-generated answer with citations in Markdown.")
    sources: List[SourceModel] = Field(..., description="All retrieved legal units cited.")
    confidence: float = Field(..., description="LLM confidence score (0.0–1.0).")
    related_laws: List[str] = Field(..., description="Laws referenced in the answer.")
    retrieval_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Debug metadata: counts per retrieval leg before and after merge.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_collection(law: Optional[str]) -> tuple[str, str]:
    """Maps a law name or identifier to (collection_name, law_identifier).

    Derives from LAW_REGISTRY so adding a new law automatically works here.
    Falls back to GDPR if no law is specified or the law is unrecognised.

    Args:
        law: Optional law name or identifier string (e.g. 'GDPR', 'dpdp').

    Returns:
        Tuple of (qdrant_collection_name, canonical_law_name).
    """
    from app.core.constants import LAW_REGISTRY, LawIdentifier

    if not law:
        # Cross-law search: default to GDPR collection for now
        # TODO: implement multi-collection fan-out when >2 active laws exist
        return "gdpr", "GDPR"

    law_upper = law.upper().replace(" ", "_").replace("-", "_")

    # Try matching by identifier value (e.g. 'gdpr', 'dpdp', 'ai_act')
    for law_id, meta in LAW_REGISTRY.items():
        if (
            law_id.value.upper() == law_upper
            or meta["name"].upper().replace(" ", "_") == law_upper
        ):
            return meta["collection_name"], meta["name"]

    # Unknown law — default to GDPR
    logger.warning(f"[Ask] Unknown law '{law}', falling back to GDPR collection.")
    return "gdpr", "GDPR"


def _build_fallback_answer(results: List[Dict[str, Any]]) -> str:
    """Builds a plain-text answer when LLM is unavailable."""
    if not results:
        return "No matching legal sources were found for your question."

    lines = [f"Retrieved {len(results)} relevant legal source(s) (LLM not configured):\n"]
    for rec in results:
        article = rec.get("article") or rec.get("id")
        title = rec.get("title") or ""
        law = rec.get("law") or ""
        text = rec.get("text", "")[:400]
        lines.append(f"### {article} — {title} ({law})\n{text}...\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("", response_model=AskResponse)
@router.post("/", response_model=AskResponse)
async def ask_question(request: AskRequest) -> AskResponse:
    """Answers a legal question using Hybrid Graph + Vector RAG pipeline."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    question = request.question.strip()
    law_filter = request.law.upper() if request.law else None
    collection, canonical_law = _infer_collection(law_filter)

    logger.info(f"[Ask] Question: {question!r} | Law filter: {law_filter} | Collection: {collection}")

    # ------------------------------------------------------------------
    # Step 1: Vector search
    # ------------------------------------------------------------------
    vector_results = await run_in_threadpool(
        vector_search,
        query=question,
        collection_name=collection,
        top_k=request.top_k,
        law_filter=law_filter,
    )

    # Extract node IDs from vector hits to seed graph traversal
    vector_hit_ids = [r["id"] for r in vector_results if r.get("id")]

    # ------------------------------------------------------------------
    # Step 2: Graph traversal (seeded by vector hits + explicit mentions)
    # ------------------------------------------------------------------
    graph_results = await run_in_threadpool(
        graph_search_by_query,
        query=question,
        law=canonical_law,
        collection_name=collection,
        vector_hit_ids=vector_hit_ids,
    )

    # ------------------------------------------------------------------
    # Step 3: Keyword / exact-match search
    # ------------------------------------------------------------------
    kw_results = await run_in_threadpool(
        keyword_search,
        query=question,
        law_filter=law_filter,
        limit=6,
    )

    # ------------------------------------------------------------------
    # Step 4: Merge and rank
    # ------------------------------------------------------------------
    merged = merge_and_rank(
        vector_results=vector_results,
        graph_results=graph_results,
        keyword_results=kw_results,
        top_k=12,
    )

    retrieval_summary = {
        "vector_hits": len(vector_results),
        "graph_hits": len(graph_results),
        "keyword_hits": len(kw_results),
        "merged_total": len(merged),
    }
    logger.info(f"[Ask] Retrieval summary: {retrieval_summary}")

    if not merged:
        logger.warning("[Ask] No results retrieved from any leg.")
        return AskResponse(
            answer="No matching legal sources were found for your question. Please try rephrasing.",
            sources=[],
            confidence=0.0,
            related_laws=[],
            retrieval_summary=retrieval_summary,
        )

    # ------------------------------------------------------------------
    # Step 5: LLM answer generation
    # ------------------------------------------------------------------
    try:
        llm_answer = await run_in_threadpool(generate_answer, question, merged)
    except RuntimeError as e:
        logger.error(f"[Ask] LLM generation failed: {e}")
        raise HTTPException(status_code=502, detail=f"LLM generation error: {e}")

    # Build sources list from merged results
    sources = [
        SourceModel(
            id=r["id"],
            article=r.get("article"),
            title=r.get("title"),
            law=r.get("law") or "Unknown",
            url=r.get("url") or "",
            retrieval_sources=r.get("retrieval_sources") or [r.get("retrieval_source", "")],
            score=r.get("score", 0.0),
        )
        for r in merged
        if r.get("url")  # only include sources that have a citable URL
    ]

    if llm_answer:
        return AskResponse(
            answer=llm_answer.answer,
            sources=sources,
            confidence=llm_answer.confidence,
            related_laws=llm_answer.related_laws,
            retrieval_summary=retrieval_summary,
        )

    # LLM not configured — return fallback text answer
    fallback = _build_fallback_answer(merged)
    related = sorted({r.get("law", "") for r in merged if r.get("law")})
    return AskResponse(
        answer=fallback,
        sources=sources,
        confidence=0.4,
        related_laws=related,
        retrieval_summary=retrieval_summary,
    )
