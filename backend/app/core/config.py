"""Application configuration module.

This module defines all application settings loaded from environment variables.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env file
# Root path is two levels up from this file's folder (backend/)
base_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=base_dir / ".env")


class Settings(BaseModel):
    """Application settings, validated using Pydantic."""

    # Server Configuration
    PORT: int = Field(default=8000)
    HOST: str = Field(default="0.0.0.0")
    ENVIRONMENT: str = Field(default="development")

    # Neo4j Configuration
    NEO4J_URI: str = Field(default="bolt://localhost:7687")
    NEO4J_USERNAME: str = Field(default="neo4j")
    NEO4J_PASSWORD: str = Field(default="testpassword123")
    NEO4J_DATABASE: Optional[str] = Field(default=None)

    # Qdrant Configuration
    QDRANT_URL: str = Field(default="http://localhost:6333")
    QDRANT_API_KEY: Optional[str] = Field(default=None)

    # LLM Configuration
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_BASE_URL: Optional[str] = Field(default=None)
    OPENAI_MODEL: Optional[str] = Field(default=None)
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    LLM_MODEL: str = Field(default="claude-3-5-sonnet-20241022")

    # Embedding Configuration
    EMBEDDING_MODEL: str = Field(default="BAAI/bge-small-en-v1.5")
    EMBEDDING_DIMENSION: int = Field(default=384)

    # Data Directory Paths (relative to backend or absolute)
    DATA_DIR: str = Field(default="../data")

    @property
    def raw_data_dir(self) -> Path:
        """Returns Path object for raw data directory."""
        path = Path(self.DATA_DIR) / "raw"
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def normalized_data_dir(self) -> Path:
        """Returns Path object for normalized data directory."""
        path = Path(self.DATA_DIR) / "normalized"
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


# Create settings instance
# We populate it with environment variables if present, falling back to defaults
settings = Settings(
    PORT=int(os.environ.get("PORT", "8000")),
    HOST=os.environ.get("HOST", "0.0.0.0"),
    ENVIRONMENT=os.environ.get("ENVIRONMENT", "development"),
    NEO4J_URI=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
    NEO4J_USERNAME=os.environ.get("NEO4J_USERNAME", "neo4j"),
    NEO4J_PASSWORD=os.environ.get("NEO4J_PASSWORD", "testpassword123"),
    NEO4J_DATABASE=os.environ.get("NEO4J_DATABASE") or None,
    QDRANT_URL=os.environ.get("QDRANT_URL", "http://localhost:6333"),
    QDRANT_API_KEY=os.environ.get("QDRANT_API_KEY") or None,
    ANTHROPIC_API_KEY=os.environ.get("ANTHROPIC_API_KEY") or None,
    OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY") or None,
    OPENAI_BASE_URL=os.environ.get("BASE_URL") or os.environ.get("OPENAI_BASE_URL") or None,
    OPENAI_MODEL=os.environ.get("OPENAI_MODEL") or None,
    GEMINI_API_KEY=os.environ.get("GEMINI_API_KEY") or None,
    LLM_MODEL=os.environ.get("LLM_MODEL", "claude-3-5-sonnet-20241022"),
    EMBEDDING_MODEL=os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
    EMBEDDING_DIMENSION=int(os.environ.get("EMBEDDING_DIMENSION", "384")),
    DATA_DIR=os.environ.get("DATA_DIR", "../data"),
)
