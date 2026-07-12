"""Graph API endpoint.

Serves graph structure data to the frontend for interactive visualization.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.graph.client import neo4j_client

router = APIRouter()


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


@router.get("", response_model=GraphDataResponse)
@router.get("/", response_model=GraphDataResponse)
async def get_graph_data(law: Optional[str] = Query(None, description="Optional law to filter by (e.g. 'GDPR')")) -> GraphDataResponse:
    """Returns the legal knowledge graph from Neo4j for interactive UI."""
    try:
        # Establish connection if needed
        neo4j_client.connect()

        parameters = {}
        where_clause = ""
        rel_where_clause = ""
        
        if law:
            # Normalize prefix to lowercase
            law_prefix = f"{law.lower()}:"
            parameters["law"] = law
            parameters["law_prefix"] = law_prefix
            
            where_clause = """
            WHERE n.law = $law 
               OR n.name = $law 
               OR (n:Chapter AND n.id STARTS WITH $law_prefix)
               OR (n:Definition AND n.law = $law)
               OR (n:Concept)
            """
            
            rel_where_clause = """
            WHERE (s.law = $law OR s.name = $law OR (s:Chapter AND s.id STARTS WITH $law_prefix) OR (s:Definition AND s.law = $law) OR (s:Concept))
              AND (t.law = $law OR t.name = $law OR (t:Chapter AND t.id STARTS WITH $law_prefix) OR (t:Definition AND t.law = $law) OR (t:Concept))
            """

        node_query = f"""
        MATCH (n)
        {where_clause}
        RETURN labels(n) as labels, properties(n) as properties
        LIMIT 1000
        """
        node_records = neo4j_client.execute_query(node_query, parameters)

        rel_query = f"""
        MATCH (s)-[r]->(t)
        {rel_where_clause}
        RETURN 
            s.id as s_id, s.name as s_name,
            t.id as t_id, t.name as t_name,
            type(r) as type, properties(r) as properties
        LIMIT 1500
        """
        rel_records = neo4j_client.execute_query(rel_query, parameters)

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

