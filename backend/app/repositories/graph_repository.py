from typing import Any, Dict, List, Optional, Tuple
from app.db.graph.client import neo4j_client
from app.core.config import settings

class GraphRepository:
    """Repository handling all Neo4j graph operations."""

    def __init__(self) -> None:
        pass

    async def get_nodes_and_edges(self, law: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Fetches the legal knowledge graph nodes and edges from Neo4j, applying an optional law filter."""
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
        LIMIT {settings.GRAPH_NODE_LIMIT}
        """
        node_records = neo4j_client.execute_query(node_query, parameters)

        rel_query = f"""
        MATCH (s)-[r]->(t)
        {rel_where_clause}
        RETURN 
            s.id as s_id, s.name as s_name,
            t.id as t_id, t.name as t_name,
            type(r) as type, properties(r) as properties
        LIMIT {settings.GRAPH_EDGE_LIMIT}
        """
        rel_records = neo4j_client.execute_query(rel_query, parameters)

        return node_records, rel_records
