from typing import Any, Dict, List, Optional, Tuple
from app.db.graph.client import neo4j_client
from app.core.config import settings

class GraphRepository:
    """Repository handling all Neo4j graph operations."""

    def __init__(self) -> None:
        pass

    async def get_nodes_and_edges(
        self, law: Optional[str] = None, limit: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Fetches connected knowledge graph nodes and edges from Neo4j, strictly scoped to a law if specified."""
        neo4j_client.connect()

        max_edges = limit or settings.GRAPH_EDGE_LIMIT
        parameters: Dict[str, Any] = {"limit": max_edges}

        if law:
            law_upper = law.upper()
            law_lower = law.lower()
            parameters["law_upper"] = law_upper
            parameters["law_lower"] = law_lower
            parameters["law_prefix"] = f"{law_lower}:"

            # Match relationships where either source or target belongs strictly to the requested law
            rel_query = f"""
            MATCH (s)-[r]->(t)
            WHERE (
                toUpper(coalesce(s.law, '')) = $law_upper 
                OR s.name = $law_upper
                OR toLower(s.id) STARTS WITH $law_prefix
                OR (s:Definition AND toUpper(coalesce(s.law, '')) = $law_upper)
            ) AND (
                toUpper(coalesce(t.law, '')) = $law_upper 
                OR t.name = $law_upper
                OR toLower(t.id) STARTS WITH $law_prefix
                OR (t:Definition AND toUpper(coalesce(t.law, '')) = $law_upper)
                OR t:Concept
            )
            RETURN 
                labels(s) as s_labels, properties(s) as s_props,
                labels(t) as t_labels, properties(t) as t_props,
                type(r) as type, properties(r) as r_props
            LIMIT $limit
            """
        else:
            rel_query = f"""
            MATCH (s)-[r]->(t)
            RETURN 
                labels(s) as s_labels, properties(s) as s_props,
                labels(t) as t_labels, properties(t) as t_props,
                type(r) as type, properties(r) as r_props
            LIMIT $limit
            """

        rel_records = neo4j_client.execute_query(rel_query, parameters)

        nodes_map: Dict[str, Dict[str, Any]] = {}
        edge_records: List[Dict[str, Any]] = []

        for rec in rel_records:
            s_props = rec.get("s_props") or {}
            t_props = rec.get("t_props") or {}
            s_labels = rec.get("s_labels") or []
            t_labels = rec.get("t_labels") or []

            s_id = s_props.get("id") or s_props.get("name")
            t_id = t_props.get("id") or t_props.get("name")

            if not s_id or not t_id:
                continue

            s_id_str = str(s_id)
            t_id_str = str(t_id)

            if s_id_str not in nodes_map:
                nodes_map[s_id_str] = {
                    "labels": s_labels,
                    "properties": s_props,
                }
            if t_id_str not in nodes_map:
                nodes_map[t_id_str] = {
                    "labels": t_labels,
                    "properties": t_props,
                }

            edge_records.append(
                {
                    "s_id": s_id_str,
                    "t_id": t_id_str,
                    "type": rec.get("type") or "RELATED",
                    "properties": rec.get("r_props") or {},
                }
            )

        # Fallback if no relationships exist for the law: fetch standalone nodes
        if not nodes_map and law:
            fallback_query = f"""
            MATCH (n)
            WHERE toUpper(coalesce(n.law, '')) = $law_upper 
               OR n.name = $law_upper 
               OR toLower(n.id) STARTS WITH $law_prefix
            RETURN labels(n) as labels, properties(n) as properties
            LIMIT {settings.GRAPH_NODE_LIMIT}
            """
            fallback_records = neo4j_client.execute_query(fallback_query, parameters)
            node_list = []
            for rec in fallback_records:
                props = rec.get("properties") or {}
                node_id = props.get("id") or props.get("name")
                if node_id:
                    node_list.append({"labels": rec.get("labels") or [], "properties": props})
            return node_list, []

        node_records = list(nodes_map.values())
        return node_records, edge_records

