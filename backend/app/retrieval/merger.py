"""Result merger module.

Implements the ranked merge / dedup step of hybrid retrieval (Step 6 context.md).
Combines vector, graph, and keyword results into a single de-duplicated, ranked
context list. The merge is deterministic and logged so behaviour is inspectable.
"""

from typing import Any, Dict, List

from app.core.logging import logger


# Source priority weights — higher = more trusted signal
_SOURCE_WEIGHTS: Dict[str, float] = {
    "vector": 1.0,    # Semantic match — primary signal
    "graph": 0.8,     # Legally-connected — strong structural signal
    "keyword": 0.5,   # Exact text match — supplementary signal
}


def merge_and_rank(
    vector_results: List[Dict[str, Any]],
    graph_results: List[Dict[str, Any]],
    keyword_results: List[Dict[str, Any]],
    top_k: int = 12,
) -> List[Dict[str, Any]]:
    """Merges three result sets, deduplicates by node ID, and ranks by weighted score.

    Scoring formula per node:
      final_score = max(weighted score from each source that returned this node)
    If the same node appears in multiple sources, its highest weighted score wins
    and its `retrieval_source` field lists all sources that found it.

    Args:
        vector_results: Results from the vector search leg.
        graph_results: Results from the graph traversal leg.
        keyword_results: Results from the keyword search leg.
        top_k: Maximum number of results to return.

    Returns:
        Sorted, deduplicated list of result dicts with merged metadata.
    """
    # Map: node_id -> merged entry
    merged: Dict[str, Dict[str, Any]] = {}

    def _add(results: List[Dict[str, Any]], source: str) -> None:
        weight = _SOURCE_WEIGHTS.get(source, 0.5)
        for item in results:
            node_id = item.get("id", "")
            if not node_id:
                continue
            weighted_score = round(item.get("score", 0) * weight, 4)
            if node_id not in merged:
                merged[node_id] = {**item, "score": weighted_score, "retrieval_sources": [source]}
            else:
                existing = merged[node_id]
                # Accumulate all sources that found this node
                if source not in existing["retrieval_sources"]:
                    existing["retrieval_sources"].append(source)
                # Keep the highest weighted score across sources
                if weighted_score > existing["score"]:
                    existing["score"] = weighted_score

    _add(vector_results, "vector")
    _add(graph_results, "graph")
    _add(keyword_results, "keyword")

    # Sort by score descending
    ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:top_k]

    # Log merge summary (inspectable per agents.md §5)
    source_breakdown = {
        "vector": sum(1 for r in ranked if "vector" in r.get("retrieval_sources", [])),
        "graph": sum(1 for r in ranked if "graph" in r.get("retrieval_sources", [])),
        "keyword": sum(1 for r in ranked if "keyword" in r.get("retrieval_sources", [])),
        "multi": sum(1 for r in ranked if len(r.get("retrieval_sources", [])) > 1),
    }
    logger.info(
        f"[Merger] Merged {len(vector_results)}V + {len(graph_results)}G + "
        f"{len(keyword_results)}K → {len(merged)} unique → top {len(ranked)} after dedup. "
        f"Breakdown: {source_breakdown}"
    )

    return ranked
