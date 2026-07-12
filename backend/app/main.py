"""FastAPI Application Entrypoint.

Sets up the application, registers routes, and configures middlewares.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ask, documents, graph, health, laws
from app.core.config import settings
from app.core.logging import logger

app = FastAPI(
    title="Legal Knowledge Graph RAG API",
    description="FastAPI service for answering legal questions with hybrid Graph + Vector RAG.",
    version="1.0.0",
)

# Configure CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes with versioned prefix
app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
app.include_router(ask.router, prefix="/api/v1/ask", tags=["Ask"])
app.include_router(graph.router, prefix="/api/v1/graph", tags=["Graph"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(laws.router, prefix="/api/v1/laws", tags=["Laws"])


@app.on_event("startup")
async def startup_event() -> None:
    """FastAPI startup handler."""
    logger.info("Starting Legal Knowledge Graph RAG API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Data Directory: {settings.DATA_DIR}")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """FastAPI shutdown handler."""
    logger.info("Shutting down Legal Knowledge Graph RAG API...")
