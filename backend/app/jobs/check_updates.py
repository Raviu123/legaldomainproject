"""Law update checker job.

Checks whether any active law has been amended or updated at its source URL.
Uses HTTP conditional requests (ETag / Last-Modified) to detect changes without
re-downloading the full document.

This job is designed to run on a recurring schedule (e.g. daily at 3am).
When a change is detected, it logs a warning and optionally triggers the
refresh_law job.

How "changed" is detected:
  1. Fetch current ETag / Last-Modified headers from the source URL.
  2. Compare against the stored value in data/cache/law_versions.json.
  3. If different → mark as stale and trigger re-ingestion.

To add a new law to update checking:
  - Ensure it has a 'source_url' in LAW_REGISTRY and its status is ACTIVE.
  - This job automatically picks it up from the registry.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from app.core.constants import LAW_REGISTRY, LawIdentifier, LawStatus
from app.core.config import settings
from app.core.logging import logger


_VERSION_CACHE_FILE = settings.cache_dir / "law_versions.json"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "LegalGraphRAG-Bot/1.0 (automated update checker)"
    )
}


def _load_version_cache() -> Dict[str, Any]:
    """Loads the stored HTTP version metadata from disk."""
    if not _VERSION_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(_VERSION_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"[UpdateChecker] Failed to load version cache: {exc}")
        return {}


def _save_version_cache(cache: Dict[str, Any]) -> None:
    """Persists the HTTP version metadata to disk."""
    try:
        _VERSION_CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"[UpdateChecker] Failed to save version cache: {exc}")


def _check_law_updated(law_id: str, source_url: str, cache: Dict[str, Any]) -> bool:
    """Checks if a law's source document has been updated via HTTP headers.

    Args:
        law_id: The law identifier string (e.g. 'gdpr').
        source_url: The URL to check.
        cache: The current version cache dict (mutated in-place on change detection).

    Returns:
        True if the source appears to have changed; False otherwise.
    """
    stored = cache.get(law_id, {})
    stored_etag: Optional[str] = stored.get("etag")
    stored_last_modified: Optional[str] = stored.get("last_modified")

    request_headers = dict(_HEADERS)
    if stored_etag:
        request_headers["If-None-Match"] = stored_etag
    if stored_last_modified:
        request_headers["If-Modified-Since"] = stored_last_modified

    try:
        with httpx.Client(headers=request_headers, follow_redirects=True, timeout=15.0) as client:
            response = client.head(source_url)
    except Exception as exc:
        logger.warning(f"[UpdateChecker] HEAD request failed for '{law_id}' ({source_url}): {exc}")
        return False

    if response.status_code == 304:
        logger.info(f"[UpdateChecker] '{law_id}' → not modified (304).")
        return False

    new_etag = response.headers.get("etag")
    new_last_modified = response.headers.get("last-modified")

    changed = False
    if new_etag and new_etag != stored_etag:
        logger.warning(f"[UpdateChecker] '{law_id}' ETag changed: {stored_etag!r} → {new_etag!r}")
        changed = True
    elif new_last_modified and new_last_modified != stored_last_modified:
        logger.warning(
            f"[UpdateChecker] '{law_id}' Last-Modified changed: "
            f"{stored_last_modified!r} → {new_last_modified!r}"
        )
        changed = True
    else:
        logger.info(f"[UpdateChecker] '{law_id}' → no change detected.")

    # Update cache regardless (persist current headers)
    cache[law_id] = {
        "etag": new_etag,
        "last_modified": new_last_modified,
        "http_status": response.status_code,
    }
    return changed


def check_all_law_updates(auto_reingest: bool = False) -> Dict[str, bool]:
    """Checks all ACTIVE laws for updates at their source URLs.

    Args:
        auto_reingest: If True, trigger re-ingestion for stale laws.

    Returns:
        Dict mapping law identifier string to a boolean (True = updated/stale).
    """
    logger.info("[UpdateChecker] Starting law update check for all ACTIVE laws...")
    cache = _load_version_cache()
    results: Dict[str, bool] = {}

    for law_id, meta in LAW_REGISTRY.items():
        if meta.get("status") != LawStatus.ACTIVE:
            continue

        source_url: str = meta.get("source_url", "")
        if not source_url:
            logger.warning(f"[UpdateChecker] No source_url for '{law_id.value}'. Skipping.")
            continue

        changed = _check_law_updated(law_id.value, source_url, cache)
        results[law_id.value] = changed

        if changed and auto_reingest:
            logger.info(f"[UpdateChecker] Triggering re-ingestion for '{law_id.value}'...")
            from app.ingestion.run import run_pipeline
            try:
                run_pipeline(law_id, skip_fetch=False)
            except Exception as exc:
                logger.error(f"[UpdateChecker] Re-ingestion failed for '{law_id.value}': {exc}")

    _save_version_cache(cache)
    stale_count = sum(1 for v in results.values() if v)
    logger.info(
        f"[UpdateChecker] Check complete. {len(results)} laws checked, "
        f"{stale_count} potentially stale."
    )
    return results
