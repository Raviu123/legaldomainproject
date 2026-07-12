"""Knowledge Graph Schema and Loader.

Defines Neo4j queries and loading routines to populate the graph from LegalUnit models.
Implements Step 3–4 of context.md.
"""

import re

from app.core.constants import RelationshipType
from app.core.logging import logger, neo4j_logger
from app.graph.client import Neo4jClient
from app.models.legal_unit import LegalUnit


def clean_term_for_id(term: str) -> str:
    """Helper to clean a term to use as a unique ID slug."""
    clean = term.lower().strip()
    clean = re.sub(r"[^a-z0-9\s_-]", "", clean)
    clean = re.sub(r"[\s-]+", "_", clean)
    return clean


def load_legal_unit_to_graph(client: Neo4jClient, unit: LegalUnit) -> None:
    """Loads a single LegalUnit (Article or Recital) into the Neo4j Graph.

    Args:
        client: The Neo4j client instance.
        unit: The LegalUnit model to load.
    """
    law_name = unit.law
    law_prefix = law_name.lower()

    neo4j_logger.info(f"Loading legal unit to graph: ID={unit.id}, Law={law_name}")

    # 1. Create the Law root node
    client.execute_query("MERGE (l:Law {name: $law_name}) RETURN l", {"law_name": law_name})

    # 2. Setup Chapter and link to Law
    # Normalize chapter ID (e.g. 'gdpr:chap_ii')
    chap_slug = clean_term_for_id(unit.chapter)
    chap_id = f"{law_prefix}:chap_{chap_slug}"

    chapter_query = """
    MERGE (c:Chapter {id: $chap_id})
    ON CREATE SET c.name = $chapter_name
    ON MATCH SET c.name = $chapter_name
    WITH c
    MATCH (l:Law {name: $law_name})
    MERGE (l)-[:HAS_CHAPTER]->(c)
    """
    client.execute_query(
        chapter_query, {"chap_id": chap_id, "chapter_name": unit.chapter, "law_name": law_name}
    )

    # 3. Create Article or Recital Node and link to Chapter
    is_recital = unit.chapter.lower() == "recitals"
    node_label = "Recital" if is_recital else "Article"

    unit_query = f"""
    MERGE (n:{node_label} {{id: $id}})
    ON CREATE SET 
        n.law = $law,
        n.article = $article,
        n.title = $title,
        n.text = $text,
        n.url = $url,
        n.source = $source,
        n.stub = false
    ON MATCH SET 
        n.law = $law,
        n.article = $article,
        n.title = $title,
        n.text = $text,
        n.url = $url,
        n.source = $source,
        n.stub = false
    WITH n
    MATCH (c:Chapter {{id: $chap_id}})
    MERGE (c)-[:HAS_ARTICLE]->(n)
    """
    client.execute_query(
        unit_query,
        {
            "id": unit.id,
            "law": law_name,
            "article": unit.article,
            "title": unit.title,
            "text": unit.text,
            "url": unit.url,
            "source": unit.source,
            "chap_id": chap_id,
        },
    )

    # 4. Load Definitions (if any) and link to Article
    if unit.definitions:
        neo4j_logger.info(f"Loading {len(unit.definitions)} definitions for Article {unit.article}...")
    for definition in unit.definitions:
        term_slug = clean_term_for_id(definition.term)
        def_id = f"{law_prefix}:def_{term_slug}"

        def_query = """
        MERGE (d:Definition {id: $def_id})
        ON CREATE SET d.term = $term, d.definition = $definition, d.law = $law
        ON MATCH SET d.definition = $definition
        WITH d
        MATCH (a:Article {id: $art_id})
        MERGE (a)-[:DEFINES]->(d)
        """
        client.execute_query(
            def_query,
            {
                "def_id": def_id,
                "term": definition.term,
                "definition": definition.definition,
                "law": law_name,
                "art_id": unit.id,
            },
        )


def load_references_and_concepts(client: Neo4jClient, unit: LegalUnit) -> None:
    """Loads cross-references and concepts for a legal unit.

    Must run after all units' base nodes are created to avoid creating permanent stubs.

    Args:
        client: The Neo4j client instance.
        unit: The LegalUnit model to load.
    """
    # 1. Load Cross-References
    if unit.references:
        neo4j_logger.info(f"Linking {len(unit.references)} references for unit {unit.id}...")
    for ref_id in unit.references:
        # Create a stub node if the target article/recital does not exist yet.
        # It determines the label dynamically based on id prefix/suffix.
        target_label = "Recital" if "recital" in ref_id.lower() else "Article"

        ref_query = f"""
        MERGE (target:{target_label} {{id: $target_id}})
        ON CREATE SET target.stub = true
        WITH target
        MATCH (source {{id: $source_id}})
        MERGE (source)-[:{RelationshipType.REFERENCES.value}]->(target)
        """
        client.execute_query(ref_query, {"source_id": unit.id, "target_id": ref_id})

    # 2. Load Concepts
    if unit.concepts:
        neo4j_logger.info(f"Linking {len(unit.concepts)} concepts for unit {unit.id}...")
    for concept in unit.concepts:
        concept_query = f"""
        MERGE (c:Concept {{name: $concept_name}})
        WITH c
        MATCH (source {{id: $source_id}})
        MERGE (source)-[:{RelationshipType.HAS_CONCEPT.value}]->(c)
        """
        client.execute_query(concept_query, {"source_id": unit.id, "concept_name": concept})


def verify_graph_integrity(client: Neo4jClient) -> None:
    """Validates the graph's integrity and prints diagnostics to the console.

    Checks for:
    - Stub nodes (referenced but never ingested)
    - Orphan nodes (nodes without relations)
    """
    logger.info("=== Verifying Knowledge Graph Integrity ===")

    # 1. Check for Stub Nodes
    stubs = client.execute_query("MATCH (n {stub: true}) RETURN n.id as id, labels(n) as labels")
    if stubs:
        logger.warning(f"Found {len(stubs)} stub nodes (referenced but not loaded):")
        for stub in stubs[:5]:
            logger.warning(f"  * Stub ID: {stub['id']} (Labels: {stub['labels']})")
    else:
        logger.info("No dangling reference stub nodes found.")

    # 2. Check for Orphan Articles/Recitals/Definitions
    orphans = client.execute_query(
        "MATCH (n) WHERE NOT (n)--() AND (n:Article OR n:Recital OR n:Definition) RETURN n.id as id"
    )
    if orphans:
        logger.warning(f"Found {len(orphans)} orphan nodes:")
        for orphan in orphans[:5]:
            logger.warning(f"  * Orphan ID: {orphan['id']}")
    else:
        logger.info("No orphan structural nodes found.")

    # 3. Print Count Summary
    summary = client.execute_query("MATCH (n) RETURN labels(n) as label, count(n) as count")
    logger.info("Graph Node Summary:")
    for row in summary:
        logger.info(f"  - {row['label']}: {row['count']}")
