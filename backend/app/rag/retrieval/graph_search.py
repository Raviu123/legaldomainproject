"""Graph Search retrieval module.

Implements Step 6 (hybrid retrieval — graph leg) from context.md.
Uses Neo4j anchor nodes (seeded by vector hit IDs or explicit article mentions)
and expands outward via DEFINES, REFERENCES, HAS_EXCEPTION, HAS_CONCEPT edges
to find legally-connected content that pure semantic search would miss.
"""

import re
from typing import Any, Dict, List

from app.core.constants import NodeLabel
from app.core.logging import logger
from app.db.graph.client import neo4j_client


# Regex to parse article/recital/section numbers from a user query
_ARTICLE_NUMBER_PATTERN = re.compile(
    r"\b(?:article|art\.?)\s*(\d+[a-z]?)\b",
    re.IGNORECASE,
)
_RECITAL_NUMBER_PATTERN = re.compile(
    r"\b(?:recital)\s*(\d+)\b",
    re.IGNORECASE,
)


def _build_law_prefix(law: str) -> str:
    """Derives the Neo4j id prefix for a given law name (e.g. 'GDPR' -> 'gdpr')."""
    return law.lower().replace(" ", "_").replace("-", "_")


def _extract_anchor_ids_from_query(query: str, law: str) -> List[str]:
    """Extracts explicit article/recital references from the query and maps to Neo4j IDs.

    E.g. 'Article 6 of GDPR' → 'gdpr:art6'.
    """
    prefix = _build_law_prefix(law)
    anchor_ids = []

    for match in _ARTICLE_NUMBER_PATTERN.finditer(query):
        num = match.group(1).lower()
        anchor_ids.append(f"{prefix}:art{num}")

    for match in _RECITAL_NUMBER_PATTERN.finditer(query):
        num = match.group(1)
        anchor_ids.append(f"{prefix}:recital{num}")

    return anchor_ids


def graph_search_from_anchors(
    anchor_ids: List[str],
    depth: int = 2,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """Traverses the graph outward from anchor node IDs.

    Expands via REFERENCES, DEFINES, HAS_CONCEPT, HAS_EXCEPTION edges up to
    `depth` hops to surface legally-connected content.

    Args:
        anchor_ids: List of Neo4j node IDs to use as starting points.
        depth: Maximum traversal depth (default 2 = anchor + 1 hop out).
        limit: Maximum number of nodes to return.

    Returns:
        List of dicts with node properties and retrieval metadata.
    """
    if not anchor_ids:
        return []

    logger.info(f"[GraphSearch] Expanding from {len(anchor_ids)} anchor IDs: {anchor_ids}")

    # Traverse outward through legally meaningful edges
    traversal_query = """
    UNWIND $anchor_ids AS anchor_id
    MATCH (anchor {id: anchor_id})
    CALL apoc.path.subgraphNodes(
        anchor,
        {
            maxLevel: $depth,
            relationshipFilter: "REFERENCES>|DEFINES>|HAS_CONCEPT>|HAS_EXCEPTION>|<HAS_ARTICLE",
            labelFilter: "+Article|+Recital|+Definition|+Concept"
        }
    ) YIELD node
    WHERE node.text IS NOT NULL
    RETURN DISTINCT
        node.id         AS id,
        node.law        AS law,
        node.chapter    AS chapter,
        node.article    AS article,
        node.title      AS title,
        node.text       AS text,
        node.url        AS url,
        labels(node)[0] AS label
    LIMIT $limit
    """

    # Fallback query without APOC in case APOC is not installed
    fallback_query = """
    UNWIND $anchor_ids AS anchor_id
    MATCH (anchor {id: anchor_id})
    OPTIONAL MATCH (anchor)-[:REFERENCES]->(ref)
    WHERE ref.text IS NOT NULL
    OPTIONAL MATCH (anchor)-[:DEFINES]->(def)
    OPTIONAL MATCH (anchor)<-[:HAS_ARTICLE]-(chap)-[:HAS_ARTICLE]->(sibling)
    WHERE sibling.text IS NOT NULL AND sibling.id <> anchor_id
    WITH collect(anchor) + collect(ref) + collect(sibling) AS nodes
    UNWIND nodes AS node
    WHERE node IS NOT NULL AND node.text IS NOT NULL
    RETURN DISTINCT
        node.id         AS id,
        node.law        AS law,
        node.chapter    AS chapter,
        node.article    AS article,
        node.title      AS title,
        node.text       AS text,
        node.url        AS url,
        labels(node)[0] AS label
    LIMIT $limit
    """

    params = {"anchor_ids": anchor_ids, "depth": depth, "limit": limit}

    records = []
    try:
        # Try APOC traversal first
        records = neo4j_client.execute_query(traversal_query, params)
        logger.info(f"[GraphSearch] APOC traversal returned {len(records)} nodes.")
    except Exception as apoc_err:
        logger.warning(f"[GraphSearch] APOC not available ({apoc_err}), using fallback traversal.")
        try:
            records = neo4j_client.execute_query(fallback_query, params)
            logger.info(f"[GraphSearch] Fallback traversal returned {len(records)} nodes.")
        except Exception as e:
            logger.error(f"[GraphSearch] Graph traversal failed: {e}")
            return []

    results = []
    for rec in records:
        if not rec.get("id"):
            continue
        results.append(
            {
                "id": rec["id"],
                "law": rec.get("law", ""),
                "chapter": rec.get("chapter", ""),
                "article": rec.get("article", ""),
                "title": rec.get("title", ""),
                "text": rec.get("text", ""),
                "url": rec.get("url", ""),
                "concepts": [],
                "score": 0.75,  # Fixed graph-traversal relevance score
                "retrieval_source": "graph",
            }
        )

    return results


def graph_search_by_query(
    query: str,
    law: str = "GDPR",
    collection_name: str = "gdpr",
    vector_hit_ids: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """Combines query-based anchor detection and vector-seeded graph expansion.

    Args:
        query: The user's natural language question.
        law: The law name to scope anchor ID inference (e.g. 'GDPR').
        collection_name: Collection name hint for logging.
        vector_hit_ids: Node IDs from the vector search leg to use as additional anchors.

    Returns:
        Deduplicated list of graph-retrieved result dicts.
    """
    # 1. Detect explicit article references from the query text
    query_anchors = _extract_anchor_ids_from_query(query, law)

    # 2. Merge with vector-seeded anchor IDs (dedup)
    all_anchors = list(dict.fromkeys(query_anchors + (vector_hit_ids or [])))
    logger.info(
        f"[GraphSearch] Anchors: {len(query_anchors)} from query, "
        f"{len(vector_hit_ids or [])} from vector hits → {len(all_anchors)} total."
    )

    if not all_anchors:
        logger.info("[GraphSearch] No anchor IDs found. Skipping graph traversal.")
        return []

    return graph_search_from_anchors(all_anchors, depth=2, limit=15)
