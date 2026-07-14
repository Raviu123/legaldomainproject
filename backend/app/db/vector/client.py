"""Qdrant client manager.

Handles the connection to the Qdrant database and the initialization/recreation of collections.
"""

from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import settings
from app.core.logging import qdrant_logger


class QdrantClientManager:
    """Singleton manager for Qdrant client connection and collection initialization."""

    _instance: Optional["QdrantClientManager"] = None

    def __new__(cls) -> "QdrantClientManager":
        if cls._instance is None:
            cls._instance = super(QdrantClientManager, cls).__new__(cls)
            cls._instance._client = None
        return cls._instance

    @property
    def client(self) -> QdrantClient:
        """Returns the Qdrant client, initializing it if necessary."""
        if self._client is None:
            url = settings.QDRANT_URL
            qdrant_logger.info(f"Connecting to Qdrant at {url}...")
            try:
                self._client = QdrantClient(
                    url=url,
                    api_key=settings.QDRANT_API_KEY,
                )
                qdrant_logger.info("Connected to Qdrant successfully.")
            except Exception as e:
                qdrant_logger.error(f"Failed to connect to Qdrant: {e}")
                raise
        return self._client

    def init_collection(self, collection_name: str, vector_size: int, force_recreate: bool = False) -> None:
        """Ensures that the collection exists in Qdrant with correct dimensions.

        Args:
            collection_name: Name of the Qdrant collection.
            vector_size: Size/dimension of the vector embeddings.
            force_recreate: If True, delete the existing collection and create a new one.
        """
        from qdrant_client.models import Distance, VectorParams

        exists = False
        try:
            self.client.get_collection(collection_name)
            exists = True
        except (UnexpectedResponse, Exception):
            exists = False

        if exists and not force_recreate:
            qdrant_logger.info(f"Collection '{collection_name}' already exists. Skipping creation.")
            return

        if exists and force_recreate:
            qdrant_logger.info(f"Deleting existing collection '{collection_name}' as force_recreate=True...")
            try:
                self.client.delete_collection(collection_name=collection_name)
            except Exception as e:
                qdrant_logger.warning(f"Failed to delete collection '{collection_name}': {e}")

        qdrant_logger.info(f"Creating Qdrant collection: '{collection_name}' (dimension: {vector_size})...")
        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            qdrant_logger.info(f"Collection '{collection_name}' created successfully.")
        except Exception as e:
            qdrant_logger.error(f"Failed to create collection '{collection_name}': {e}")
            raise


# Global instance
qdrant_client_manager = QdrantClientManager()
