"""Crawler module.

Handles fetching raw HTML or PDF documents from official sources and caching them locally.
"""

import time
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.logging import logger

# Default headers to mimic a browser
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_and_cache(url: str, filename: str, force_refetch: bool = False) -> Path:
    """Fetches a URL and caches it to the raw data directory.

    Args:
        url: The URL to fetch.
        filename: The filename to save as under raw/ (e.g. 'gdpr_raw.html').
        force_refetch: If True, refetches even if cached.

    Returns:
        Path: The path to the cached file.
    """
    raw_dir = settings.raw_data_dir
    cache_path = raw_dir / filename

    if cache_path.exists() and not force_refetch:
        logger.info(f"Using cached file: {cache_path}")
        return cache_path

    logger.info(f"Fetching: {url}")
    try:
        # Respectful rate limiting: wait 1 second before requesting
        time.sleep(1.0)

        with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()

            # Save raw content
            # If it's a binary file (e.g., PDF), save as bytes. Otherwise, save as text.
            if filename.endswith(".pdf"):
                cache_path.write_bytes(response.content)
            else:
                cache_path.write_text(response.text, encoding="utf-8")

            logger.info(f"Successfully cached raw file to {cache_path}")
            return cache_path
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        raise
