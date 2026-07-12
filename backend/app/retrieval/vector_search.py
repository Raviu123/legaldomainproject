"""Vector Search retrieval module.

Implements Step 6 (hybrid retrieval — vector leg) from context.md.
Embeds the user query using the local BGE model and retrieves the top-k
most semantically similar legal units from Qdrant.
"""

import re
from typing import Any, Dict, List

from app.core.config import settings
from app.core.logging import logger
from app.vector.client import qdrant_client_manager
from app.vector.embeddings import embedding_model


# Regex to detect explicit article/recital references in a query
_ARTICLE_REF_PATTERN = re.compile(
    r"\b(article|recital|section|art\.?|sec\.?)\s*(\d+[a-z]?)\b",
    re.IGNORECASE,
)


def extract_article_mentions(query: str) -> List[str]:
    """Extracts explicit article/recital number mentions from the user query.

    Returns a list of normalised mention strings like ['article 6', 'recital 14'].
    """
    return [f"{m.group(1).lower()} {m.group(2)}" for m in _ARTICLE_REF_PATTERN.finditer(query)]


def vector_search(
    query: str,
    collection_name: str,
    top_k: int = 8,
    law_filter: str | None = None,
) -> List[Dict[str, Any]]:
    """Embeds the query and retrieves top-k similar legal units from Qdrant.

    Args:
        query: The user's natural language question.
        collection_name: The Qdrant collection to search (e.g. 'gdpr').
        top_k: Maximum number of results to return.
        law_filter: Optional law name to filter results (e.g. 'GDPR').

    Returns:
        List of dicts with keys: id, law, chapter, article, title, text,
        url, concepts, score, retrieval_source.
    """
    logger.info(f"[VectorSearch] Embedding query for collection '{collection_name}'...")

    try:
        query_vector = embedding_model.embed_query(query)
    except Exception as e:
        logger.error(f"[VectorSearch] Failed to embed query: {e}")
        return []

    # Build optional payload filter
    qdrant_filter = None
    if law_filter:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        qdrant_filter = Filter(
            must=[FieldCondition(key="law", match=MatchValue(value=law_filter))]
        )

    try:
        client = qdrant_client_manager.client

        # qdrant-client v2.x uses query_points(); v1.x used search()
        try:
            response = client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
                with_vectors=False,
            )
            hits = response.points
        except AttributeError:
            # Fallback for older qdrant-client v1.x
            hits = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
                with_vectors=False,
            )
    except Exception as e:
        logger.error(f"[VectorSearch] Qdrant search failed: {e}")
        return []

    results = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(
            {
                "id": payload.get("id", ""),
                "law": payload.get("law", ""),
                "chapter": payload.get("chapter", ""),
                "article": payload.get("article", ""),
                "title": payload.get("title", ""),
                "text": payload.get("text", ""),
                "url": payload.get("url", ""),
                "concepts": payload.get("concepts", []),
                "score": round(hit.score, 4),
                "retrieval_source": "vector",
            }
        )

    logger.info(f"[VectorSearch] Retrieved {len(results)} results (top score: {results[0]['score'] if results else 'N/A'}).")
    return results
