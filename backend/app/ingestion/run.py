"""Ingestion pipeline CLI.

This is the single entrypoint for all ingestion jobs, regardless of the law.
It dispatches to the correct parser via the registry, runs all pipeline stages,
and writes results to Neo4j and Qdrant.

Usage:
    # Full pipeline for GDPR
    python -m app.ingestion.run --law gdpr

    # Skip heavy re-download if raw file already cached
    python -m app.ingestion.run --law gdpr --skip-fetch

    # Skip graph loading (useful when only refreshing vectors)
    python -m app.ingestion.run --law gdpr --skip-graph

    # Force recreate Qdrant collection (wipes existing embeddings)
    python -m app.ingestion.run --law gdpr --force-recreate-vector

    # Dry run — parse and enrich only, don't load any database
    python -m app.ingestion.run --law gdpr --dry-run

Pipeline stages (in order):
    1. Fetch & cache raw source file             (crawler)
    2. Parse raw file → List[LegalUnit]          (parser registry)
    3. Enrich: extract references + definitions  (structure_extractor)
    4. Enrich: extract semantic concepts         (entity_extractor)
    5. Validate & save to normalized JSON        (normalizer)
    6. Load into Neo4j knowledge graph           (graph/schema)
    7. Embed & load into Qdrant vector store     (vector/schema)
    8. Verify graph integrity                    (graph/schema)
"""

import argparse
import asyncio
import sys
from typing import Optional

from app.core.constants import LAW_REGISTRY, LawIdentifier
from app.core.logging import logger
from app.extraction.entity_extractor import extract_concepts
from app.extraction.structure_extractor import enrich_legal_structure
from app.db.graph.client import neo4j_client
from app.db.graph.schema import (
    load_legal_unit_to_graph,
    load_references_and_concepts,
    verify_graph_integrity,
)
from app.ingestion.crawler import fetch_and_cache, RobustWebCrawler
from app.ingestion.normalizer import normalize_and_save
from app.ingestion.registry import get_parser
from app.models.legal_unit import LegalUnit
from app.db.vector.schema import load_legal_units_to_vector_db


def run_pipeline(
    law: LawIdentifier,
    *,
    skip_fetch: bool = False,
    skip_graph: bool = False,
    skip_vector: bool = False,
    skip_relational: bool = False,
    use_crawl4ai: bool = False,
    force_recreate_vector: bool = False,
    dry_run: bool = False,
) -> None:
    """Run the full ingestion pipeline for any registered law.

    Args:
        law: The LawIdentifier for the law to ingest.
        skip_fetch: If True, reuse the existing cached raw file (skip HTTP request).
        skip_graph: If True, skip the Neo4j loading stages.
        skip_vector: If True, skip the Qdrant embedding and loading stage.
        force_recreate_vector: If True, delete and recreate the Qdrant collection.
        dry_run: If True, only run parse + enrich stages; do not write to any DB.
    """
    law_meta = LAW_REGISTRY.get(law)
    if law_meta is None:
        logger.error(f"Law '{law.value}' is not in LAW_REGISTRY. Add it to constants.py first.")
        sys.exit(1)

    law_name = law_meta["name"]
    source_url: str = law_meta["source_url"]
    source_type: str = law_meta["source_type"]
    collection_name: str = law_meta["collection_name"]

    logger.info(f"{'=' * 60}")
    logger.info(f"  Ingestion Pipeline — {law_name} ({law.value})")
    logger.info(f"{'=' * 60}")

    # ------------------------------------------------------------------
    # Stage 1: Fetch & cache raw source file
    # ------------------------------------------------------------------
    raw_filename = f"{law.value}_raw.{source_type}"
    logger.info(f"[Stage 1] Fetching raw source → {raw_filename}")

    if skip_fetch:
        from app.core.config import settings
        raw_file_path = settings.raw_data_dir / raw_filename
        if not raw_file_path.exists():
            logger.error(
                f"[Stage 1] skip_fetch=True but cached file not found: {raw_file_path}. "
                "Run without --skip-fetch to download it first."
            )
            sys.exit(1)
        logger.info(f"[Stage 1] Using cached file: {raw_file_path}")
    else:
        try:
            if use_crawl4ai:
                logger.info(f"[Stage 1] Instantiating crawl4ai RobustWebCrawler for {source_url}...")
                crawler = RobustWebCrawler(
                    base_url=source_url,
                    max_depth=2,
                    max_pages=100,
                    politeness_delay=1.0,
                )
                raw_file_path = asyncio.run(crawler.crawl(raw_filename))
            else:
                raw_file_path = fetch_and_cache(source_url, raw_filename, force_refetch=True)
        except Exception as exc:
            logger.error(f"[Stage 1] Crawling failed: {exc}")
            sys.exit(1)

    # ------------------------------------------------------------------
    # Stage 2: Parse raw file → List[LegalUnit]
    # ------------------------------------------------------------------
    logger.info("[Stage 2] Parsing raw source file...")
    parser = get_parser(law)
    try:
        units = parser.parse(raw_file_path, source_url, law)
    except NotImplementedError as exc:
        logger.error(f"[Stage 2] Parser not implemented: {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"[Stage 2] Parsing failed: {exc}")
        raise

    logger.info(f"[Stage 2] Parsed {len(units)} legal units.")

    # ------------------------------------------------------------------
    # Stage 3: Enrich — extract definitions and cross-references
    # ------------------------------------------------------------------
    logger.info("[Stage 3] Extracting legal structure (definitions & references)...")
    units = enrich_legal_structure(units)

    # ------------------------------------------------------------------
    # Stage 4: Enrich — extract semantic concepts
    # ------------------------------------------------------------------
    logger.info("[Stage 4] Extracting semantic concepts (hybrid regex + LLM)...")
    for idx, unit in enumerate(units):
        if idx % 50 == 0 or idx == len(units) - 1:
            logger.info(f"  Concepts: {idx + 1}/{len(units)} units processed...")
        unit.concepts = extract_concepts(unit.text, unit.id)

    # ------------------------------------------------------------------
    # Stage 5: Validate and persist normalized JSON
    # ------------------------------------------------------------------
    normalized_filename = f"{law.value}.json"
    logger.info(f"[Stage 5] Saving normalized data → {normalized_filename}")
    normalize_and_save(units, normalized_filename)

    if dry_run:
        logger.info("[DryRun] Stages 6-8 skipped. Dry run complete.")
        _log_summary(units, law_name)
        return

    # ------------------------------------------------------------------
    # Stage 6: Load into Neo4j knowledge graph (two-pass)
    # ------------------------------------------------------------------
    if skip_graph:
        logger.info("[Stage 6] Skipping Neo4j graph load (--skip-graph).")
    else:
        logger.info("[Stage 6] Loading into Neo4j knowledge graph...")
        try:
            neo4j_client.connect()
            neo4j_client.setup_constraints()

            logger.info("  Pass 1/2: Merging base nodes (Law → Chapter → Article/Recital/Definition)...")
            for unit in units:
                load_legal_unit_to_graph(neo4j_client, unit)

            logger.info("  Pass 2/2: Linking relationships (REFERENCES, HAS_CONCEPT)...")
            for unit in units:
                load_references_and_concepts(neo4j_client, unit)

        except Exception as exc:
            logger.error(f"[Stage 6] Graph loading failed: {exc}")
            raise
        finally:
            neo4j_client.close()

    # ------------------------------------------------------------------
    # Stage 7: Embed and load into Qdrant vector store
    # ------------------------------------------------------------------
    if skip_vector:
        logger.info("[Stage 7] Skipping Qdrant vector load (--skip-vector).")
    else:
        logger.info(f"[Stage 7] Loading into Qdrant collection '{collection_name}'...")
        try:
            load_legal_units_to_vector_db(
                units,
                collection_name=collection_name,
                force_recreate=force_recreate_vector,
            )
        except Exception as exc:
            logger.error(f"[Stage 7] Vector loading failed: {exc}")
            raise

    # ------------------------------------------------------------------
    # Stage 7.5: Load into PostgreSQL relational database
    # ------------------------------------------------------------------
    if skip_relational:
        logger.info("[Stage 7.5] Skipping PostgreSQL relational load (--skip-relational).")
    else:
        logger.info("[Stage 7.5] Loading into PostgreSQL relational database...")
        try:
            from app.db.relational import LawDb, LegalUnitDb, upsert_law_metadata, bulk_upsert_legal_units
            from app.db.relational.connection import async_session

            # Map constants LAW_REGISTRY values
            meta = LAW_REGISTRY[law]
            law_meta = LawDb(
                id=meta["identifier"].value,
                name=meta["name"],
                full_name=meta["full_name"],
                description=meta.get("description", ""),
                jurisdiction=meta["jurisdiction"].value,
                status=meta["status"].value,
                source_url=meta.get("source_url", ""),
                categories=[c.value for c in meta.get("categories", [])],
            )

            db_units = [
                LegalUnitDb(
                    id=u.id,
                    law=u.law,
                    chapter=u.chapter,
                    article=u.article,
                    section=u.section,
                    title=u.title,
                    text=u.text,
                    source=u.source,
                    url=u.url,
                    definitions=[d.model_dump() for d in u.definitions],
                    concepts=u.concepts,
                    references=u.references
                )
                for u in units
            ]

            async def _load():
                async with async_session() as session:
                    await upsert_law_metadata(session, law_meta)
                    await bulk_upsert_legal_units(session, db_units)

            asyncio.run(_load())
            logger.info("[Stage 7.5] Successfully loaded into PostgreSQL.")
        except Exception as exc:
            logger.error(f"[Stage 7.5] PostgreSQL loading failed: {exc}")
            raise

    # ------------------------------------------------------------------
    # Stage 8: Verify graph integrity
    # ------------------------------------------------------------------
    if not skip_graph:
        logger.info("[Stage 8] Verifying graph integrity...")
        try:
            neo4j_client.connect()
            verify_graph_integrity(neo4j_client)
        except Exception as exc:
            logger.warning(f"[Stage 8] Graph verification encountered issues: {exc}")
        finally:
            neo4j_client.close()

    _log_summary(units, law_name)


def _log_summary(units: list[LegalUnit], law_name: str) -> None:
    """Logs a summary of ingested units."""
    recitals = [u for u in units if u.chapter.lower() == "recitals"]
    articles = [u for u in units if u.chapter.lower() != "recitals"]
    total_refs = sum(len(u.references) for u in units)
    total_concepts = sum(len(u.concepts) for u in units)
    total_definitions = sum(len(u.definitions) for u in units)

    logger.info(f"{'=' * 60}")
    logger.info(f"  Pipeline Complete — {law_name}")
    logger.info(f"  Total units    : {len(units)}")
    logger.info(f"  Recitals       : {len(recitals)}")
    logger.info(f"  Articles       : {len(articles)}")
    logger.info(f"  References     : {total_refs}")
    logger.info(f"  Definitions    : {total_definitions}")
    logger.info(f"  Concepts       : {total_concepts}")
    logger.info(f"{'=' * 60}")


def main() -> None:
    """CLI entrypoint."""
    registered_laws = [law.value for law in LawIdentifier]

    parser = argparse.ArgumentParser(
        description="Legal Knowledge Graph — Ingestion Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Registered laws: {', '.join(registered_laws)}",
    )
    parser.add_argument(
        "--law",
        type=str,
        required=True,
        choices=registered_laws,
        metavar="LAW",
        help="Law identifier to ingest (e.g. gdpr, dpdp, ai_act).",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Reuse existing cached raw file; skip HTTP download.",
    )
    parser.add_argument(
        "--skip-graph",
        action="store_true",
        help="Skip Neo4j graph loading stages.",
    )
    parser.add_argument(
        "--skip-vector",
        action="store_true",
        help="Skip Qdrant vector loading stage.",
    )
    parser.add_argument(
        "--skip-relational",
        action="store_true",
        help="Skip PostgreSQL relational database loading stage.",
    )
    parser.add_argument(
        "--use-crawl4ai",
        action="store_true",
        help="Use Crawl4AI robust asynchronous web crawler.",
    )
    parser.add_argument(
        "--force-recreate-vector",
        action="store_true",
        help="Delete and recreate the Qdrant collection before loading.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run parse + enrich only; write nothing to any database.",
    )

    args = parser.parse_args()

    try:
        law_id = LawIdentifier(args.law)
    except ValueError:
        logger.error(f"Unknown law identifier: '{args.law}'")
        sys.exit(1)

    run_pipeline(
        law=law_id,
        skip_fetch=args.skip_fetch,
        skip_graph=args.skip_graph,
        skip_vector=args.skip_vector,
        skip_relational=args.skip_relational,
        use_crawl4ai=args.use_crawl4ai,
        force_recreate_vector=args.force_recreate_vector,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
