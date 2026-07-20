"""Graph API endpoint.

Serves graph structure data to the frontend for interactive visualization.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from app.services.graph_service import GraphService, GraphDataResponse

router = APIRouter()


def get_graph_service() -> GraphService:
    """Dependency provider for GraphService."""
    return GraphService()


@router.get("", response_model=GraphDataResponse)
@router.get("/", response_model=GraphDataResponse)
async def get_graph_data(
    law: Optional[str] = Query(None, description="Optional law to filter by (e.g. 'GDPR')"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Max edge limit for visualization."),
    graph_service: GraphService = Depends(get_graph_service),
) -> GraphDataResponse:
    """Returns the legal knowledge graph from Neo4j for interactive UI."""
    return await graph_service.get_graph_data(law=law, limit=limit)


