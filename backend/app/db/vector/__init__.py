"""Vector Database module using Qdrant and local SentenceTransformer embeddings.
"""

from app.db.vector.client import qdrant_client_manager
from app.db.vector.embeddings import embedding_model
from app.db.vector.schema import load_legal_units_to_vector_db

__all__ = [
    "qdrant_client_manager",
    "embedding_model",
    "load_legal_units_to_vector_db",
]
