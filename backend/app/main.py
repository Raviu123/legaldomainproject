"""FastAPI Application Entrypoint.

Registers all routers, configures middlewares, and manages startup / shutdown
lifecycle events (database connections, background schedulers, etc.).

Route map:
  GET  /api/v1/health             — Liveness check
  GET  /api/v1/health/llm         — LLM connectivity check
  POST /api/v1/ask                — Hybrid RAG query endpoint
  GET  /api/v1/graph              — Knowledge graph data for visualization
  GET  /api/v1/documents          — List ingested laws
  GET  /api/v1/documents/{law}    — All units for a specific law
  GET  /api/v1/laws               — Law catalog with ingestion status
  GET  /api/v1/laws/{law_id}      — Articles for a specific law
  GET  /api/v1/admin/registry     — List all laws in the registry (admin)
  POST /api/v1/admin/ingest       — Trigger ingestion pipeline (admin)
  POST /api/v1/admin/check-updates — Trigger update check (admin)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, ask, documents, graph, health, laws
from app.core.config import settings
from app.core.logging import logger

app = FastAPI(
    title="Legal Knowledge Graph RAG API",
    description=(
        "FastAPI service answering legal questions using hybrid Graph + Vector RAG "
        "across GDPR, DPDP Act, AI Act, and 50+ global privacy and regulatory laws."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middlewares
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT != "production" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health.router,    prefix="/api/v1/health",     tags=["Health"])
app.include_router(ask.router,       prefix="/api/v1/ask",        tags=["Ask"])
app.include_router(graph.router,     prefix="/api/v1/graph",      tags=["Graph"])
app.include_router(documents.router, prefix="/api/v1/documents",  tags=["Documents"])
app.include_router(laws.router,      prefix="/api/v1/laws",       tags=["Laws"])
app.include_router(admin.router,     prefix="/api/v1/admin",      tags=["Admin"])

# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup_event() -> None:
    """FastAPI startup — log config, optionally warm up connections."""
    logger.info("=" * 60)
    logger.info("Legal Knowledge Graph RAG API — starting up")
    logger.info(f"  Environment : {settings.ENVIRONMENT}")
    logger.info(f"  Data Dir    : {settings.DATA_DIR}")
    logger.info(f"  Neo4j URI   : {settings.NEO4J_URI}")
    logger.info(f"  Qdrant URL  : {settings.QDRANT_URL}")
    logger.info(f"  LLM Model   : {settings.LLM_MODEL}")
    logger.info(f"  Embed Model : {settings.EMBEDDING_MODEL}")
    logger.info("=" * 60)

    # Initialize relational database tables
    from app.db.relational import init_db
    await init_db()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """FastAPI shutdown — close long-lived connections."""
    logger.info("Legal Knowledge Graph RAG API — shutting down.")
    from app.db.graph.client import neo4j_client
    neo4j_client.close()
