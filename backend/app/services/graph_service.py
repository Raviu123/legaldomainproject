from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException

from app.repositories.graph_repository import GraphRepository

class GraphNode(BaseModel):
    """Pydantic model representing a Graph Node."""

    id: str = Field(..., description="Unique node identifier.")
    label: str = Field(..., description="Node label/class (e.g. 'Article', 'Concept').")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Custom node properties.")


class GraphRelationship(BaseModel):
    """Pydantic model representing a Graph Relationship/Edge."""

    source: str = Field(..., description="ID of the source node.")
    target: str = Field(..., description="ID of the target node.")
    type: str = Field(..., description="Relationship type (e.g. 'REFERENCES').")
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Custom relationship properties."
    )


class GraphDataResponse(BaseModel):
    """Response model containing nodes and edges for visualization."""

    nodes: List[GraphNode]
    edges: List[GraphRelationship]


class GraphService:
    """Service to handle fetching and formatting knowledge graph data."""

    def __init__(self, graph_repo: GraphRepository = None) -> None:
        self.graph_repo = graph_repo or GraphRepository()

    async def get_graph_data(self, law: Optional[str] = None) -> GraphDataResponse:
        """Fetches the legal knowledge graph from Neo4j, formatted for visualization."""
        try:
            node_records, rel_records = await self.graph_repo.get_nodes_and_edges(law)

            nodes = []
            for rec in node_records:
                labels = rec.get("labels") or []
                label = labels[0] if labels else "Unknown"
                props = rec.get("properties") or {}

                # Determine unique business key
                node_id = props.get("id") or props.get("name")
                if not node_id:
                    continue

                nodes.append(GraphNode(id=str(node_id), label=label, properties=props))

            edges = []
            for rec in rel_records:
                s_id = rec.get("s_id") or rec.get("s_name")
                t_id = rec.get("t_id") or rec.get("t_name")
                rel_type = rec.get("type") or "UNKNOWN"
                rel_props = rec.get("properties") or {}

                if s_id and t_id:
                    edges.append(
                        GraphRelationship(
                            source=str(s_id),
                            target=str(t_id),
                            type=rel_type,
                            properties=rel_props
                        )
                    )

            return GraphDataResponse(nodes=nodes, edges=edges)

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch graph data from Neo4j database: {str(e)}"
            )
