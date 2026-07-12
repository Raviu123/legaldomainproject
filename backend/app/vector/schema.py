"""Qdrant Ingestor.

Embeds LegalUnit objects and loads them into a Qdrant collection with appropriate payload structure.
"""

import uuid
from typing import List
from qdrant_client.models import PointStruct

from app.core.logging import logger, qdrant_logger
from app.models.legal_unit import LegalUnit
from app.vector.client import qdrant_client_manager
from app.vector.embeddings import embedding_model


def get_deterministic_uuid(unit_id: str) -> str:
    """Generates a stable UUID based on the legal unit ID to support idempotent upserts."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, unit_id))


def get_document_text(unit: LegalUnit) -> str:
    """Builds the text to embed, combining metadata (Article/Title) with the actual text.

    This ensures that vector matching can search over headers and titles alongside content.
    """
    parts = []
    if unit.article:
        parts.append(unit.article)
    if unit.title:
        parts.append(unit.title)
    header = " - ".join(parts)
    if header:
        return f"{header}\n\n{unit.text}"
    return unit.text


def load_legal_units_to_vector_db(
    units: List[LegalUnit], collection_name: str, force_recreate: bool = False
) -> None:
    """Embeds and loads a list of LegalUnit objects into Qdrant.

    Args:
        units: List of LegalUnit models.
        collection_name: Name of the Qdrant collection to populate.
        force_recreate: Whether to clear/delete the collection first.
    """
    logger.info(
        f"=== Starting Qdrant Ingestion: {len(units)} units -> collection '{collection_name}' ==="
    )

    # 1. Initialize collection (bge-small-en-v1.5 has 384 dimensions)
    # Get dimension from config settings
    from app.core.config import settings
    vector_dim = settings.EMBEDDING_DIMENSION

    qdrant_client_manager.init_collection(
        collection_name=collection_name,
        vector_size=vector_dim,
        force_recreate=force_recreate,
    )

    client = qdrant_client_manager.client

    # 2. Prepare text content and generate embeddings
    logger.info("Preparing text data for embedding...")
    texts_to_embed = [get_document_text(unit) for unit in units]

    try:
        embeddings = embedding_model.embed_documents(texts_to_embed)
    except Exception as e:
        qdrant_logger.error(f"Failed to generate embeddings: {e}")
        raise

    # 3. Create Point objects for Qdrant
    logger.info("Constructing payload points...")
    points = []
    for idx, unit in enumerate(units):
        point_id = get_deterministic_uuid(unit.id)
        vector = embeddings[idx]

        # Payload matching the LegalUnit structure and search requirements
        payload = {
            "id": unit.id,
            "law": unit.law,
            "chapter": unit.chapter,
            "article": unit.article,
            "title": unit.title,
            "text": unit.text,
            "source": unit.source,
            "url": unit.url,
            "concepts": unit.concepts,
            "references": unit.references,
            "definitions": [d.model_dump() for d in unit.definitions],
        }

        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        )

    # 4. Upsert to Qdrant in batches
    logger.info(f"Upserting {len(points)} points to Qdrant collection '{collection_name}'...")
    try:
        batch_size = 100
        total_batches = (len(points) - 1) // batch_size + 1
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            client.upsert(collection_name=collection_name, points=batch)
            qdrant_logger.info(
                f"  * Upserted batch {i // batch_size + 1}/{total_batches} ({len(batch)} points)"
            )
        logger.info(
            f"=== Qdrant Ingestion Complete: {len(units)} units ingested successfully ==="
        )
    except Exception as e:
        qdrant_logger.error(f"Qdrant loading failed: {e}")
        raise
