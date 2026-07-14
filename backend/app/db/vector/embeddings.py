"""Local Embedding Generator.

Generates embeddings locally using SentenceTransformers (default: BAAI/bge-small-en-v1.5).
"""

from typing import List, Optional
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.logging import qdrant_logger


class EmbeddingModel:
    """Manages the SentenceTransformer model instance and embedding operations."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._model: Optional[SentenceTransformer] = None

    @property
    def model(self) -> SentenceTransformer:
        """Returns the SentenceTransformer model, loading it if not already loaded."""
        if self._model is None:
            qdrant_logger.info(f"Loading local SentenceTransformer model: {self.model_name}...")
            try:
                self._model = SentenceTransformer(self.model_name)
                qdrant_logger.info(f"Successfully loaded model: {self.model_name}")
            except Exception as e:
                qdrant_logger.error(f"Failed to load embedding model '{self.model_name}': {e}")
                raise
        return self._model

    def embed_query(self, text: str) -> List[float]:
        """Embeds a search query.

        BGE models recommend prefixing the query for better search accuracy.
        """
        # For BAAI/bge-small-en-v1.5 and similar BGE models, we prefix search queries
        prefix = "Represent this sentence for searching relevant passages: "
        processed_text = text if not self.model_name.startswith("BAAI/bge-") else f"{prefix}{text}"
        
        qdrant_logger.info(f"Generating embedding for query (length={len(text)})...")
        embedding = self.model.encode(processed_text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embeds a list of documents. No query prefix is required here."""
        qdrant_logger.info(f"Generating embeddings for {len(texts)} documents using {self.model_name}...")
        try:
            embeddings = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            qdrant_logger.info(f"Successfully generated {len(texts)} embeddings.")
            return embeddings.tolist()
        except Exception as e:
            qdrant_logger.error(f"Failed to encode documents: {e}")
            raise


# Global instance
embedding_model = EmbeddingModel()
