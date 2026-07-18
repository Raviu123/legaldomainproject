"""Application configuration.

All settings come from environment variables (or .env file). Never hardcode
secrets, endpoints, or model names anywhere else in the codebase — import
`settings` from here instead.

To add a new configuration key:
  1. Add it as a class attribute with a sensible default and a Field description.
  2. Add the corresponding env-var mapping in the `settings` instantiation at bottom.
  3. Document it in .env.example.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Root of the backend/ directory (two levels up from this file)
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_BASE_DIR / ".env")


class Settings(BaseModel):
    """Application settings, all validated via Pydantic."""

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------
    PORT: int = Field(default=8000, description="Server port.")
    HOST: str = Field(default="0.0.0.0", description="Server bind address.")
    ENVIRONMENT: str = Field(default="development", description="'development' | 'staging' | 'production'.")

    # ------------------------------------------------------------------
    # Neo4j
    # ------------------------------------------------------------------
    NEO4J_URI: str = Field(default="bolt://localhost:7687", description="Bolt URI for Neo4j.")
    NEO4J_USERNAME: str = Field(default="neo4j", description="Neo4j username.")
    NEO4J_PASSWORD: str = Field(default="testpassword123", description="Neo4j password.")
    NEO4J_DATABASE: Optional[str] = Field(default=None, description="Named database (leave None for default).")

    # ------------------------------------------------------------------
    # Relational Database (PostgreSQL)
    # ------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:testpassword123@localhost:5432/legal_data",
        description="Async connection string for PostgreSQL."
    )

    # ------------------------------------------------------------------
    # Qdrant
    # ------------------------------------------------------------------
    QDRANT_URL: str = Field(default="http://localhost:6333", description="Qdrant REST endpoint.")
    QDRANT_API_KEY: Optional[str] = Field(default=None, description="Qdrant API key (cloud only).")

    # ------------------------------------------------------------------
    # LLM — OpenAI-compatible primary provider
    # ------------------------------------------------------------------
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI-compatible API key.")
    OPENAI_BASE_URL: Optional[str] = Field(
        default=None,
        description="Custom base URL for OpenAI-compatible APIs (NVIDIA NIM, LiteLLM, etc.).",
    )
    OPENAI_MODEL: Optional[str] = Field(
        default=None,
        description="Model name override (e.g. 'gpt-4o', 'openai/gpt-oss-120b').",
    )

    # ------------------------------------------------------------------
    # LLM — Anthropic (alternative provider)
    # ------------------------------------------------------------------
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API key.")

    # ------------------------------------------------------------------
    # LLM — Google Gemini (alternative provider)
    # ------------------------------------------------------------------
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API key.")

    # ------------------------------------------------------------------
    # Default LLM model (used when OPENAI_MODEL is not set)
    # ------------------------------------------------------------------
    LLM_MODEL: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Default LLM model identifier.",
    )

    # ------------------------------------------------------------------
    # Embeddings — local SentenceTransformer
    # ------------------------------------------------------------------
    EMBEDDING_MODEL: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="HuggingFace SentenceTransformer model name.",
    )
    EMBEDDING_DIMENSION: int = Field(
        default=384,
        description="Dimensionality of the embedding vectors (must match the model).",
    )

    # ------------------------------------------------------------------
    # Data directories (relative to project root or absolute)
    # ------------------------------------------------------------------
    DATA_DIR: str = Field(
        default="../data",
        description="Base data directory (can be relative to backend/ or absolute).",
    )

    # ------------------------------------------------------------------
    # Ingestion jobs
    # ------------------------------------------------------------------
    INGESTION_BATCH_SIZE: int = Field(
        default=50,
        description="Number of LegalUnit objects processed per batch during graph / vector loading.",
    )
    INGESTION_RATE_LIMIT_SLEEP: float = Field(
        default=1.0,
        description="Seconds to wait between HTTP requests in the crawler (polite rate limiting).",
    )

    # ------------------------------------------------------------------
    # Feature flags
    # ------------------------------------------------------------------
    ENABLE_LLM_CONCEPT_EXTRACTION: bool = Field(
        default=True,
        description="Toggle LLM-based concept extraction during ingestion (can be disabled to cut costs).",
    )
    ENABLE_APOC: bool = Field(
        default=True,
        description="Whether APOC plugin is available on the Neo4j instance.",
    )

    # ------------------------------------------------------------------
    # Graph & RAG Limits (Magic Numbers)
    # ------------------------------------------------------------------
    GRAPH_NODE_LIMIT: int = Field(
        default=1000,
        description="Max nodes fetched for visualization.",
    )
    GRAPH_EDGE_LIMIT: int = Field(
        default=1500,
        description="Max edges fetched for visualization.",
    )
    ASK_DEFAULT_TOP_K: int = Field(
        default=8,
        description="Default top_k for RAG search legs.",
    )
    ASK_MERGE_TOP_K: int = Field(
        default=12,
        description="Top_k after merging RAG search legs.",
    )
    ASK_KEYWORD_LIMIT: int = Field(
        default=6,
        description="Limit for keyword search leg.",
    )
    ASK_FALLBACK_CONFIDENCE: float = Field(
        default=0.4,
        description="Fallback confidence score when LLM is offline.",
    )

    # ------------------------------------------------------------------
    # Computed path helpers
    # ------------------------------------------------------------------

    @property
    def base_dir(self) -> Path:
        """Backend root directory."""
        return _BASE_DIR

    @property
    def raw_data_dir(self) -> Path:
        """Directory for raw (untouched) downloaded source files."""
        path = Path(self.DATA_DIR) / "raw"
        if not path.is_absolute():
            path = (_BASE_DIR / path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def normalized_data_dir(self) -> Path:
        """Directory for fully normalised JSON files (one per law)."""
        path = Path(self.DATA_DIR) / "normalized"
        if not path.is_absolute():
            path = (_BASE_DIR / path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cache_dir(self) -> Path:
        """Directory for general-purpose caches (e.g. concept_cache.json)."""
        path = Path(self.DATA_DIR) / "cache"
        if not path.is_absolute():
            path = (_BASE_DIR / path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


# Singleton settings instance — import this everywhere
settings = Settings(
    PORT=int(os.environ.get("PORT", "8000")),
    HOST=os.environ.get("HOST", "0.0.0.0"),
    ENVIRONMENT=os.environ.get("ENVIRONMENT", "development"),
    NEO4J_URI=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
    NEO4J_USERNAME=os.environ.get("NEO4J_USERNAME", "neo4j"),
    NEO4J_PASSWORD=os.environ.get("NEO4J_PASSWORD", "testpassword123"),
    NEO4J_DATABASE=os.environ.get("NEO4J_DATABASE") or None,
    DATABASE_URL=os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:testpassword123@localhost:5432/legal_data"),
    QDRANT_URL=os.environ.get("QDRANT_URL", "http://localhost:6333"),
    QDRANT_API_KEY=os.environ.get("QDRANT_API_KEY") or None,
    OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY") or None,
    OPENAI_BASE_URL=os.environ.get("BASE_URL") or os.environ.get("OPENAI_BASE_URL") or None,
    OPENAI_MODEL=os.environ.get("OPENAI_MODEL") or None,
    ANTHROPIC_API_KEY=os.environ.get("ANTHROPIC_API_KEY") or None,
    GEMINI_API_KEY=os.environ.get("GEMINI_API_KEY") or None,
    LLM_MODEL=os.environ.get("LLM_MODEL", "claude-3-5-sonnet-20241022"),
    EMBEDDING_MODEL=os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
    EMBEDDING_DIMENSION=int(os.environ.get("EMBEDDING_DIMENSION", "384")),
    DATA_DIR=os.environ.get("DATA_DIR", "../data"),
    INGESTION_BATCH_SIZE=int(os.environ.get("INGESTION_BATCH_SIZE", "50")),
    INGESTION_RATE_LIMIT_SLEEP=float(os.environ.get("INGESTION_RATE_LIMIT_SLEEP", "1.0")),
    ENABLE_LLM_CONCEPT_EXTRACTION=os.environ.get("ENABLE_LLM_CONCEPT_EXTRACTION", "true").lower() == "true",
    ENABLE_APOC=os.environ.get("ENABLE_APOC", "true").lower() == "true",
    GRAPH_NODE_LIMIT=int(os.environ.get("GRAPH_NODE_LIMIT", "1000")),
    GRAPH_EDGE_LIMIT=int(os.environ.get("GRAPH_EDGE_LIMIT", "1500")),
    ASK_DEFAULT_TOP_K=int(os.environ.get("ASK_DEFAULT_TOP_K", "8")),
    ASK_MERGE_TOP_K=int(os.environ.get("ASK_MERGE_TOP_K", "12")),
    ASK_KEYWORD_LIMIT=int(os.environ.get("ASK_KEYWORD_LIMIT", "6")),
    ASK_FALLBACK_CONFIDENCE=float(os.environ.get("ASK_FALLBACK_CONFIDENCE", "0.4")),
)
