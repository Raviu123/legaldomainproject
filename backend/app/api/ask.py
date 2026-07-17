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

def _infer_collection(law: Optional[str]) -> tuple[str, str, str]:
    """Maps a law name or identifier to (collection_name, law_identifier, db_law_string).

    Derives from LAW_REGISTRY so adding a new law automatically works here.
    Falls back to GDPR if no law is specified or the law is unrecognised.

    Args:
        law: Optional law name or identifier string (e.g. 'GDPR', 'dpdp').

    Returns:
        Tuple of (qdrant_collection_name, canonical_law_name, db_law_string).
    """
    from app.core.constants import LAW_REGISTRY, LawIdentifier

    if not law:
        # Cross-law search: default to GDPR collection for now
        # TODO: implement multi-collection fan-out when >2 active laws exist
        return "gdpr", "GDPR", "GDPR"

    law_upper = law.upper().replace(" ", "_").replace("-", "_")

    # Try matching by identifier value (e.g. 'gdpr', 'dpdp', 'ai_act')
    for law_id, meta in LAW_REGISTRY.items():
        if (
            law_id.value.upper() == law_upper
            or meta["name"].upper().replace(" ", "_") == law_upper
        ):
            return meta["collection_name"], meta["name"], meta["identifier"].value.upper()

    # Unknown law — default to GDPR
    logger.warning(f"[Ask] Unknown law '{law}', falling back to GDPR collection.")
    return "gdpr", "GDPR", "GDPR"


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

    # Detect if the query asks about other laws to automatically enable cross-law search
    from app.core.constants import LAW_REGISTRY, LawStatus
    import asyncio

    active_laws = [
        meta for meta in LAW_REGISTRY.values()
        if meta["status"] == LawStatus.ACTIVE
    ]

    question_upper = question.upper()
    mentioned_laws = []
    for meta in active_laws:
        # Match e.g. "GDPR", "DPDP", "IT ACT", "PRIVACY ACT"
        name_clean = meta["name"].upper().replace(" ACT", "")
        id_clean = meta["identifier"].value.upper()
        if name_clean in question_upper or id_clean in question_upper:
            mentioned_laws.append(meta)

    # Broaden filter to cross-law search if:
    # 1. No filter is set.
    # 2. More than one law is mentioned in the question (comparative).
    # 3. A law is mentioned in the question that is different from the active filter.
    is_cross_law = False
    if not law_filter:
        is_cross_law = True
    elif len(mentioned_laws) > 1:
        is_cross_law = True
        logger.info(f"[Ask] Query mentions multiple laws {[m['name'] for m in mentioned_laws]}. Enabling cross-law search.")
    elif len(mentioned_laws) == 1:
        # Check if the single mentioned law differs from the active filter
        single_law_name = mentioned_laws[0]["name"].upper()
        single_law_id = mentioned_laws[0]["identifier"].value.upper()
        if law_filter not in [single_law_name, single_law_id]:
            is_cross_law = True
            logger.info(f"[Ask] Query mentions a different law '{mentioned_laws[0]['name']}' than active filter '{law_filter}'. Enabling cross-law search.")

    # ------------------------------------------------------------------
    # Step 1: Vector search
    # ------------------------------------------------------------------
    if is_cross_law:
        # Check which Qdrant collections exist to avoid 404 search failures
        existing_collections = set()
        try:
            from app.db.vector.client import qdrant_client_manager
            client = qdrant_client_manager.client
            cols = client.get_collections().collections
            existing_collections = {c.name for c in cols}
        except Exception as e:
            logger.warning(f"[Ask] Failed to list Qdrant collections: {e}")

        # Determine which laws to query. If specific laws were mentioned, query only those.
        # Otherwise, query all active laws.
        laws_to_query = mentioned_laws if mentioned_laws else active_laws

        # Filter by existing collections in Qdrant to avoid 404 errors
        if existing_collections:
            filtered_laws = [
                meta for meta in laws_to_query
                if meta["collection_name"] in existing_collections
            ]
            if filtered_laws:
                laws_to_query = filtered_laws

        logger.info(f"[Ask] Running cross-law query. Querying laws: {[m['name'] for m in laws_to_query]}")
        tasks = [
            run_in_threadpool(
                vector_search,
                query=question,
                collection_name=meta["collection_name"],
                top_k=request.top_k,
                law_filter=None,
            )
            for meta in laws_to_query
        ]
        vector_results_nested = await asyncio.gather(*tasks)

        vector_results = []
        for res_list in vector_results_nested:
            vector_results.extend(res_list)

        vector_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        canonical_laws = [meta["identifier"].value.upper() for meta in laws_to_query]
        collection_log_name = "multiple"
        kw_law_filter = [meta["identifier"].value.upper() for meta in laws_to_query]
    else:
        collection, canonical_law, db_law = _infer_collection(law_filter)
        logger.info(f"[Ask] Question: {question!r} | Law filter: {law_filter} | Collection: {collection} | DB Law: {db_law}")

        vector_results = await run_in_threadpool(
            vector_search,
            query=question,
            collection_name=collection,
            top_k=request.top_k,
            law_filter=db_law,
        )
        canonical_laws = db_law
        collection_log_name = collection
        kw_law_filter = db_law

    # Extract node IDs from vector hits to seed graph traversal
    vector_hit_ids = [r["id"] for r in vector_results if r.get("id")]

    # ------------------------------------------------------------------
    # Step 2: Graph traversal (seeded by vector hits + explicit mentions)
    # ------------------------------------------------------------------
    graph_results = await run_in_threadpool(
        graph_search_by_query,
        query=question,
        law=canonical_laws,
        collection_name=collection_log_name,
        vector_hit_ids=vector_hit_ids,
    )

    # ------------------------------------------------------------------
    # Step 3: Keyword / exact-match search
    # ------------------------------------------------------------------
    kw_results = await run_in_threadpool(
        keyword_search,
        query=question,
        law_filter=kw_law_filter,
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
