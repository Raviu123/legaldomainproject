from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import BackgroundTasks, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.constants import LAW_REGISTRY, LawIdentifier, LawStatus, Jurisdiction, LawCategory
from app.core.logging import logger
from app.ingestion.run import run_pipeline
from app.jobs.check_updates import check_all_law_updates


def _ensure_law_registered(law_name: str) -> Any:
    """Ensures law_name is registered in LAW_REGISTRY dynamically if unlisted."""
    law_clean = law_name.lower().replace("-", "_").strip()
    
    # Handle common aliases
    if law_clean in ["pdpa_sg", "sg_pdpa"]:
        return LawIdentifier.PDPA_SG

    # Try finding existing LawIdentifier
    matched_id = None
    for lid in LawIdentifier:
        if lid.value == law_clean or lid.name.lower() == law_clean:
            matched_id = lid
            break

    if matched_id is None:
        matched_id = law_clean

    if matched_id not in LAW_REGISTRY:
        logger.info(f"[AdminService] Dynamically registering new custom law '{law_clean}' into LAW_REGISTRY.")
        
        jur = Jurisdiction.GLOBAL
        if "sg" in law_clean or "singapore" in law_clean:
            jur = Jurisdiction.SG
        elif "ca" in law_clean or "canada" in law_clean:
            jur = Jurisdiction.CA
        elif "jp" in law_clean or "japan" in law_clean:
            jur = Jurisdiction.JP

        # Create dynamic class/value object compatible with LawIdentifier
        class DynamicLawId(str):
            @property
            def value(self):
                return law_clean

        dynamic_id = DynamicLawId(law_clean)

        LAW_REGISTRY[dynamic_id] = {
            "identifier": dynamic_id,
            "name": law_name.upper(),
            "full_name": f"{law_name.upper()} Statutory Document",
            "jurisdiction": jur,
            "categories": [LawCategory.DATA_PRIVACY],
            "status": LawStatus.ACTIVE,
            "source_url": "",
            "source_type": "pdf",
            "collection_name": law_clean,
            "id_prefix": law_clean,
            "description": f"Dynamically registered legal framework for {law_name.upper()}.",
        }
        return dynamic_id

    return matched_id


class RegistryEntry(BaseModel):
    """Summary of a law in the registry."""

    identifier: str
    name: str
    full_name: str
    jurisdiction: str
    status: str
    source_url: str


class IngestResponse(BaseModel):
    """Response for an ingest trigger."""

    status: str
    law: str
    message: str


class AdminService:
    """Service to handle administrative tasks such as ingestion and updates checks."""

    def __init__(self) -> None:
        pass

    def list_law_registry(self) -> List[RegistryEntry]:
        """Returns all laws in the registry with their ingestion status."""
        entries = []
        for meta in LAW_REGISTRY.values():
            id_val = meta["identifier"].value if hasattr(meta["identifier"], "value") else str(meta["identifier"])
            jur_val = meta["jurisdiction"].value if hasattr(meta["jurisdiction"], "value") else str(meta["jurisdiction"])
            status_val = meta["status"].value if hasattr(meta["status"], "value") else str(meta["status"])
            
            entries.append(
                RegistryEntry(
                    identifier=id_val,
                    name=meta["name"],
                    full_name=meta["full_name"],
                    jurisdiction=jur_val,
                    status=status_val,
                    source_url=meta.get("source_url", ""),
                )
            )
        return entries

    def trigger_ingestion(self, law_name: str, skip_fetch: bool, skip_graph: bool, skip_vector: bool, force_recreate_vector: bool, dry_run: bool, background_tasks: BackgroundTasks) -> IngestResponse:
        """Triggers the ingestion pipeline for a law as a background task."""
        law_id = _ensure_law_registered(law_name)
        law_meta = LAW_REGISTRY.get(law_id)

        logger.info(f"[AdminService] Ingestion triggered for '{law_name}' via Service.")

        background_tasks.add_task(
            run_pipeline,
            law_id,
            skip_fetch=skip_fetch,
            skip_graph=skip_graph,
            skip_vector=skip_vector,
            force_recreate_vector=force_recreate_vector,
            dry_run=dry_run,
        )

        id_str = law_id.value if hasattr(law_id, "value") else str(law_id)
        return IngestResponse(
            status="accepted",
            law=id_str,
            message=(
                f"Ingestion pipeline for '{law_meta['name']}' has been queued. "
                "Monitor progress in application logs."
            ),
        )

    async def trigger_ingestion_file(
        self,
        file: UploadFile,
        law_name: str,
        skip_graph: bool,
        skip_vector: bool,
        force_recreate_vector: bool,
        dry_run: bool,
        background_tasks: BackgroundTasks,
    ) -> IngestResponse:
        """Triggers the ingestion pipeline using a directly uploaded file."""
        law_id = _ensure_law_registered(law_name)
        law_meta = LAW_REGISTRY.get(law_id)

        source_type = law_meta.get("source_type", "pdf")
        id_str = law_id.value if hasattr(law_id, "value") else str(law_id)
        filename = f"{id_str}_raw.{source_type}"
        target_path = settings.raw_data_dir / filename
        settings.raw_data_dir.mkdir(parents=True, exist_ok=True)

        contents = await file.read()
        with open(target_path, "wb") as f:
            f.write(contents)

        logger.info(
            f"[AdminService] Direct file upload saved for '{id_str}' to {target_path} ({len(contents)} bytes)."
        )

        background_tasks.add_task(
            run_pipeline,
            law_id,
            skip_fetch=True,
            skip_graph=skip_graph,
            skip_vector=skip_vector,
            force_recreate_vector=force_recreate_vector,
            dry_run=dry_run,
        )

        return IngestResponse(
            status="accepted",
            law=id_str,
            message=(
                f"File '{file.filename}' uploaded successfully for '{law_meta['name']}'. "
                "Ingestion pipeline has been queued with cached source file."
            ),
        )

    def trigger_update_check(self, auto_reingest: bool, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        """Triggers a background check for source document updates across all ACTIVE laws."""
        logger.info(f"[AdminService] Law update check triggered via Service (auto_reingest={auto_reingest}).")
        background_tasks.add_task(check_all_law_updates, auto_reingest)

        return {
            "status": "accepted",
            "message": "Update check queued. Results will be logged.",
            "auto_reingest": auto_reingest,
        }

    async def delete_law_complete(self, law_name: str) -> Dict[str, Any]:
        """Completely purges a law from Neo4j, Qdrant, PostgreSQL, disk files, and LAW_REGISTRY."""
        law_clean = law_name.lower().replace("-", "_").strip()
        
        results: Dict[str, Any] = {
            "law": law_clean,
            "neo4j": "skipped",
            "qdrant": "skipped",
            "postgres": "skipped",
            "files_removed": [],
        }

        # 1. Neo4j Graph cleanup
        try:
            from app.db.neo4j.connection import neo4j_client
            neo4j_client.connect()
            with neo4j_client.session() as session:
                query = """
                MATCH (n) WHERE UPPER(n.law) = $law_id OR n.id STARTS WITH $law_prefix
                DETACH DELETE n
                """
                res = session.run(query, law_id=law_clean.upper(), law_prefix=f"{law_clean}:")
                summary = res.consume()
                nodes_deleted = summary.counters.nodes_deleted
                results["neo4j"] = f"deleted {nodes_deleted} nodes"
            neo4j_client.close()
        except Exception as exc:
            logger.warning(f"[DeleteLaw] Neo4j purge warning for '{law_clean}': {exc}")
            results["neo4j"] = f"warning: {exc}"

        # 2. Qdrant Vector DB cleanup
        try:
            from app.db.qdrant.connection import get_qdrant_client
            qclient = get_qdrant_client()
            for coll in [law_clean, law_clean.upper(), f"collection_{law_clean}"]:
                try:
                    qclient.delete_collection(collection_name=coll)
                    results["qdrant"] = f"deleted collection '{coll}'"
                    break
                except Exception:
                    pass
        except Exception as exc:
            logger.warning(f"[DeleteLaw] Qdrant purge warning for '{law_clean}': {exc}")
            results["qdrant"] = f"warning: {exc}"

        # 3. PostgreSQL Relational DB cleanup
        try:
            from app.db.relational.connection import async_session
            from sqlalchemy import text
            async with async_session() as session:
                await session.execute(text("DELETE FROM legalunitdb WHERE UPPER(law) = :law"), {"law": law_clean.upper()})
                await session.execute(text("DELETE FROM lawdb WHERE LOWER(id) = :law"), {"law": law_clean})
                await session.commit()
                results["postgres"] = "deleted relational records"
        except Exception as exc:
            logger.warning(f"[DeleteLaw] PostgreSQL purge warning for '{law_clean}': {exc}")
            results["postgres"] = f"warning: {exc}"

        # 4. File system cache cleanup
        for pattern in [f"{law_clean}_raw.*", f"{law_clean}.json"]:
            for folder in [settings.raw_data_dir, settings.normalized_data_dir]:
                if folder.exists():
                    for fpath in folder.glob(pattern):
                        try:
                            fpath.unlink()
                            results["files_removed"].append(str(fpath.name))
                        except Exception:
                            pass

        # 5. Remove from in-memory LAW_REGISTRY
        keys_to_del = [k for k in LAW_REGISTRY.keys() if (k.value if hasattr(k, "value") else str(k)) == law_clean]
        for k in keys_to_del:
            LAW_REGISTRY.pop(k, None)

        logger.info(f"[DeleteLaw] Completed total deletion for law '{law_clean}': {results}")
        return results


