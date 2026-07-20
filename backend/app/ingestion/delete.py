"""CLI tool to completely delete a law across Neo4j, Qdrant, PostgreSQL, disk caches, and registry."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.admin_service import AdminService
from app.core.logging import logger


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Legal Knowledge Graph — Purge / Delete Law CLI",
    )
    parser.add_argument(
        "--law",
        type=str,
        required=True,
        metavar="LAW",
        help="Law identifier to delete (e.g. sg_pdpa, pdpa_sg, dpdp).",
    )

    args = parser.parse_args()
    law_id = args.law.strip()

    logger.info(f"{'=' * 60}")
    logger.info(f"  PURGING LAW: '{law_id}' across Neo4j, Qdrant, PostgreSQL, and Disk Caches")
    logger.info(f"{'=' * 60}")

    admin_service = AdminService()
    res = asyncio.run(admin_service.delete_law_complete(law_id))

    logger.info(f"Deletion summary for '{law_id}':")
    logger.info(f"  • Neo4j Graph  : {res.get('neo4j')}")
    logger.info(f"  • Qdrant Vector: {res.get('qdrant')}")
    logger.info(f"  • PostgreSQL   : {res.get('postgres')}")
    logger.info(f"  • Files Cleaned: {res.get('files_removed')}")
    logger.info(f"{'=' * 60}")
    logger.info("Purge operation finished!")


if __name__ == "__main__":
    main()
