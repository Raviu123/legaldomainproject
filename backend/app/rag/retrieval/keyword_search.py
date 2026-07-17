"""Keyword / exact-match search retrieval module.

Implements the keyword leg of Step 6 (hybrid retrieval) from context.md.
Narrows down results using Neo4j full-text scan for exact article numbers
and key legal terms. Used as a supplementary signal alongside vector + graph.
"""

import re
from typing import Any, Dict, List

from app.core.logging import logger
from app.db.graph.client import neo4j_client


def _extract_keywords(text: str) -> List[str]:
    """Extracts meaningful keywords from a query string, stripping stopwords."""
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    stopwords = {
        "the", "a", "an", "and", "or", "but", "if", "then",
        "is", "are", "was", "were", "be", "been", "being",
        "can", "could", "should", "would", "must", "may", "might",
        "in", "on", "at", "by", "for", "with", "about", "against",
        "of", "to", "from", "into", "through", "between",
        "what", "how", "why", "where", "when", "who", "whom",
        "this", "that", "these", "those", "it", "its",
        "under", "as", "per", "any", "all", "such",
    }
    return [w for w in cleaned.split() if w not in stopwords and len(w) > 2]


def keyword_search(
    query: str,
    law_filter: str | None = None,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    """Searches Neo4j for nodes whose text, title, or term fields contain query keywords.

    Uses a scoring approach: nodes matching more keywords rank higher.

    Args:
        query: The user's natural language question.
        law_filter: Optional law name to scope the search (e.g. 'GDPR').
        limit: Maximum number of results to return.

    Returns:
        List of result dicts with retrieval_source='keyword'.
    """
    keywords = _extract_keywords(query)
    if not keywords:
        logger.info("[KeywordSearch] No keywords extracted from query.")
        return []

    logger.info(f"[KeywordSearch] Searching with keywords: {keywords}")

    if law_filter:
        if isinstance(law_filter, list):
            law_clause = "AND n.law IN $law_filter"
        else:
            law_clause = "AND n.law = $law_filter"
    else:
        law_clause = ""

    # Score nodes by how many keywords appear in text/title
    cypher = f"""
    MATCH (n)
    WHERE (n:Article OR n:Recital OR n:Definition)
    AND n.text IS NOT NULL
    AND (n.stub IS NULL OR n.stub = false)
    {law_clause}
    WITH n,
        reduce(score = 0, kw IN $keywords |
            score +
            CASE WHEN toLower(n.text) CONTAINS kw THEN 1 ELSE 0 END +
            CASE WHEN n.title IS NOT NULL AND toLower(n.title) CONTAINS kw THEN 2 ELSE 0 END +
            CASE WHEN n:Definition AND n.term IS NOT NULL AND toLower(n.term) CONTAINS kw THEN 3 ELSE 0 END
        ) AS kw_score
    WHERE kw_score > 0
    RETURN
        n.id       AS id,
        n.law      AS law,
        n.chapter  AS chapter,
        n.article  AS article,
        n.title    AS title,
        n.text     AS text,
        n.url      AS url,
        kw_score   AS score
    ORDER BY kw_score DESC
    LIMIT $limit
    """

    params: Dict[str, Any] = {"keywords": keywords, "limit": limit}
    if law_filter:
        params["law_filter"] = law_filter

    try:
        records = neo4j_client.execute_query(cypher, params)
    except Exception as e:
        logger.error(f"[KeywordSearch] Query failed: {e}")
        return []

    results = []
    for rec in records:
        if not rec.get("id"):
            continue
        # Normalise keyword score to a 0–1 band below vector scores
        raw_score = rec.get("score", 0)
        normalised = min(0.6, round(raw_score / (len(keywords) * 3 + 1), 4))
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
                "score": normalised,
                "retrieval_source": "keyword",
            }
        )

    logger.info(f"[KeywordSearch] Returned {len(results)} results.")
    return results
