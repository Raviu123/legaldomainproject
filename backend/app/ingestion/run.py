"""Ingestion CLI pipeline runner.

Coordinates the sequential stages of crawling, parsing, normalizing,
extracting structure, extracting entities, loading into Neo4j graph,
and loading into Qdrant vector database.
"""

import argparse
import sys

from app.core.constants import LawName
from app.core.logging import logger
from app.extraction.entity_extractor import extract_concepts
from app.extraction.structure_extractor import enrich_legal_structure
from app.graph.client import neo4j_client
from app.graph.schema import (
    load_legal_unit_to_graph,
    load_references_and_concepts,
    verify_graph_integrity,
)
from app.ingestion.crawler.crawler import fetch_and_cache
from app.ingestion.normalizer import normalize_and_save
from app.ingestion.parsers.eur_lex import parse_eur_lex_html
from app.vector.schema import load_legal_units_to_vector_db


def run_gdpr_pipeline(
    force_refetch: bool = False,
    skip_graph: bool = False,
    skip_vector: bool = False,
    force_recreate_vector: bool = False,
) -> None:
    """Executes the ingestion pipeline for GDPR."""
    logger.info("=== Starting GDPR Ingestion Pipeline ===")

    # 1. Crawl / Fetch raw HTML
    url = "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng"
    raw_filename = "gdpr_raw.html"
    try:
        raw_file_path = fetch_and_cache(url, raw_filename, force_refetch=force_refetch)
    except Exception as e:
        logger.error(f"Crawling failed: {e}")
        sys.exit(1)

    # 2. Parse EUR-Lex HTML
    logger.info("Stage 2: Parsing raw HTML...")
    parsed_units = parse_eur_lex_html(raw_file_path, url, LawName.GDPR)
    if not parsed_units:
        logger.error("No legal units parsed from HTML. Aborting.")
        sys.exit(1)

    # 3. Extract Legal Structure (Definitions + References)
    logger.info("Stage 3: Extracting legal structures (definitions & references)...")
    enriched_units = enrich_legal_structure(parsed_units)

    # 4. Extract Semantic Concepts (Entities)
    logger.info("Stage 4: Extracting semantic concepts (hybrid regex + LLM)...")
    for idx, unit in enumerate(enriched_units):
        # Log progress for every 30 articles to avoid console flooding
        if idx % 30 == 0 or idx == len(enriched_units) - 1:
            logger.info(f"  * Extracting concepts for unit {idx + 1}/{len(enriched_units)}...")
        unit.concepts = extract_concepts(unit.text, unit.id)

    # Save fully enriched data to JSON
    normalized_filename = "gdpr.json"
    normalize_and_save(enriched_units, normalized_filename)

    # 5. Load into Neo4j Knowledge Graph
    if skip_graph:
        logger.info("Skipping Knowledge Graph load as requested.")
    else:
        logger.info("Stage 5: Loading into Neo4j Knowledge Graph...")
        try:
            # Connect to Neo4j
            neo4j_client.connect()

            # Set up constraints
            neo4j_client.setup_constraints()

            # Pass 1: Load base nodes (Law, Chapters, Articles, Recitals, Definitions)
            logger.info("  * Loading base nodes (Pass 1/2)...")
            for unit in enriched_units:
                load_legal_unit_to_graph(neo4j_client, unit)

            # Pass 2: Load relationships (REFERENCES, HAS_CONCEPT)
            logger.info("  * Linking relationships and concepts (Pass 2/2)...")
            for unit in enriched_units:
                load_references_and_concepts(neo4j_client, unit)

            # Run validation queries
            verify_graph_integrity(neo4j_client)

        except Exception as e:
            logger.error(f"Graph loading failed: {e}")
        finally:
            # Clean up connection
            neo4j_client.close()

    # 6. Load into Qdrant Vector Database
    if skip_vector:
        logger.info("Skipping Vector Database load as requested.")
    else:
        logger.info("Stage 6: Loading into Qdrant Vector Database...")
        try:
            load_legal_units_to_vector_db(
                enriched_units,
                collection_name="gdpr",
                force_recreate=force_recreate_vector,
            )
        except Exception as e:
            logger.error(f"Vector loading failed: {e}")

    logger.info("=== GDPR Ingestion Pipeline Complete ===")
    logger.info(f"Total Legal Units Processed: {len(enriched_units)}")

    recitals = [u for u in enriched_units if u.chapter == "Recitals"]
    articles = [u for u in enriched_units if u.chapter != "Recitals"]
    logger.info(f"  - Recitals: {len(recitals)}")
    logger.info(f"  - Articles: {len(articles)}")

    # Print summary statistics of definitions
    art4 = next((u for u in enriched_units if u.article == "Article 4"), None)
    if art4 and art4.definitions:
        logger.info(f"  - Definitions extracted from Article 4: {len(art4.definitions)}")


def main() -> None:
    """CLI entrypoint for running ingestion pipelines."""
    parser = argparse.ArgumentParser(description="Legal Data Ingestion Pipeline CLI")
    parser.add_argument(
        "--law",
        type=str,
        required=True,
        choices=["gdpr", "dpdp", "ai_act"],
        help="The law to ingest (e.g. 'gdpr')",
    )
    parser.add_argument(
        "--force-refetch",
        action="store_true",
        help="Force download of the raw source file, bypassing cache.",
    )
    parser.add_argument(
        "--skip-graph",
        action="store_true",
        help="Skip loading the data into Neo4j graph.",
    )
    parser.add_argument(
        "--skip-vector",
        action="store_true",
        help="Skip loading the data into Qdrant vector database.",
    )
    parser.add_argument(
        "--force-recreate-vector",
        action="store_true",
        help="Force deletion and recreation of the Qdrant collection.",
    )

    args = parser.parse_args()

    if args.law == "gdpr":
        run_gdpr_pipeline(
            force_refetch=args.force_refetch,
            skip_graph=args.skip_graph,
            skip_vector=args.skip_vector,
            force_recreate_vector=args.force_recreate_vector,
        )
    elif args.law == "dpdp":
        logger.warning("DPDP pipeline is not implemented yet. Focus is on GDPR first.")
    elif args.law == "ai_act":
        logger.warning("AI Act pipeline is not implemented yet. Focus is on GDPR first.")


if __name__ == "__main__":
    main()
