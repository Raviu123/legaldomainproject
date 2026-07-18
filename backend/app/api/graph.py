"""Graph API endpoint.

Serves graph structure data to the frontend for interactive visualization.
"""

from typing import Optional

from fastapi import APIRouter, Query
from app.services.graph_service import GraphService, GraphDataResponse

router = APIRouter()
graph_service = GraphService()


@router.get("", response_model=GraphDataResponse)
@router.get("/", response_model=GraphDataResponse)
async def get_graph_data(
    law: Optional[str] = Query(None, description="Optional law to filter by (e.g. 'GDPR')")
) -> GraphDataResponse:
    """Returns the legal knowledge graph from Neo4j for interactive UI."""
    return await graph_service.get_graph_data(law)
