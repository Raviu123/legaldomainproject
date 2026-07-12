"""Neo4j Database Client.

Manages connection lifecycle and provides query execution wrappers with detailed query logging.
"""

from typing import Any, Dict, List, Optional

from neo4j import Driver, GraphDatabase

from app.core.config import settings
from app.core.logging import logger, neo4j_logger


class Neo4jClient:
    """Singleton client to interact with Neo4j Database."""

    _instance: Optional["Neo4jClient"] = None

    def __new__(cls) -> "Neo4jClient":
        if cls._instance is None:
            cls._instance = super(Neo4jClient, cls).__new__(cls)
            cls._instance._driver = None
        return cls._instance

    def connect(self) -> None:
        """Establishes connection to the Neo4j database."""
        if self._driver is not None:
            return

        uri = settings.NEO4J_URI
        username = settings.NEO4J_USERNAME
        password = settings.NEO4J_PASSWORD

        neo4j_logger.info(f"Connecting to Neo4j database at {uri}...")
        try:
            self._driver = GraphDatabase.driver(uri, auth=(username, password))
            # Verify the connectivity
            self._driver.verify_connectivity()
            neo4j_logger.info("Connected to Neo4j successfully.")
        except Exception as e:
            neo4j_logger.error(f"Failed to connect to Neo4j: {e}")
            self._driver = None
            raise

    def close(self) -> None:
        """Closes the driver connection."""
        if self._driver:
            neo4j_logger.info("Closing Neo4j connection...")
            self._driver.close()
            self._driver = None

    @property
    def driver(self) -> Driver:
        """Returns the active Driver instance, establishing connection if needed."""
        if self._driver is None:
            self.connect()
        assert self._driver is not None
        return self._driver

    def execute_query(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Executes a Cypher query and returns the results as a list of dicts.

        Args:
            query: The Cypher query to execute.
            parameters: The parameters for the query.

        Returns:
            List[Dict[str, Any]]: List of record mappings.
        """
        parameters = parameters or {}
        cleaned_query = " ".join(query.strip().split())
        neo4j_logger.info(f"Executing Cypher: {cleaned_query} | Params: {parameters}")
        
        try:
            session_args = {}
            if settings.NEO4J_DATABASE:
                session_args["database"] = settings.NEO4J_DATABASE
            with self.driver.session(**session_args) as session:
                result = session.run(query, parameters)
                records = [record.data() for record in result]
                neo4j_logger.info(f"Query returned {len(records)} records.")
                return records
        except Exception as e:
            neo4j_logger.error(f"Error executing Cypher query: {e}\nQuery: {query}\nParams: {parameters}")
            raise

    def setup_constraints(self) -> None:
        """Creates unique constraints for nodes to ensure data integrity."""
        neo4j_logger.info("Setting up database constraints...")

        # Constraints list (using IF NOT EXISTS syntax supported in Neo4j 5+)
        constraints = [
            (
                "CREATE CONSTRAINT law_name_unique IF NOT EXISTS "
                "FOR (l:Law) REQUIRE l.name IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT chapter_id_unique IF NOT EXISTS "
                "FOR (c:Chapter) REQUIRE c.id IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT article_id_unique IF NOT EXISTS "
                "FOR (a:Article) REQUIRE a.id IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT recital_id_unique IF NOT EXISTS "
                "FOR (r:Recital) REQUIRE r.id IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT definition_id_unique IF NOT EXISTS "
                "FOR (d:Definition) REQUIRE d.id IS UNIQUE"
            ),
            (
                "CREATE CONSTRAINT concept_name_unique IF NOT EXISTS "
                "FOR (c:Concept) REQUIRE c.name IS UNIQUE"
            ),
        ]

        for constraint in constraints:
            try:
                self.execute_query(constraint)
            except Exception as e:
                # Fallback in case constraint name is not supported or needs a different format
                neo4j_logger.warning(f"Could not apply constraint query '{constraint}': {e}")


# Global client instance
neo4j_client = Neo4jClient()
