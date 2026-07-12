"""Retrieval package.

Exposes the three independently-callable retrieval legs and the merger
as described in context.md §6 and agents.md §5.
"""

from app.retrieval.graph_search import graph_search_by_query
from app.retrieval.keyword_search import keyword_search
from app.retrieval.merger import merge_and_rank
from app.retrieval.vector_search import vector_search

__all__ = [
    "vector_search",
    "graph_search_by_query",
    "keyword_search",
    "merge_and_rank",
]
