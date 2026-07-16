"""Crawl4AI robust web crawler.

Asynchronous crawler that recursively follows links, executes JavaScript,
and caches pages either as cleaned HTML or Markdown.
"""

import asyncio
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import Set, List

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler

from app.core.config import settings
from app.core.logging import logger


class RobustWebCrawler:
    """Robust web crawler using Crawl4AI for dynamic rendering and link discovery."""

    def __init__(
        self,
        base_url: str,
        max_depth: int = 2,
        max_pages: int = 100,
        politeness_delay: float = 1.0,
    ):
        """Initializes the crawler.

        Args:
            base_url: The starting seed URL.
            max_depth: Maximum recursion depth for link discovery.
            max_pages: Maximum absolute limit of pages to crawl.
            politeness_delay: Seconds to sleep between page fetches.
        """
        self.base_url = base_url
        self.parsed_base = urlparse(base_url)
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.politeness_delay = politeness_delay

        self.visited_urls: Set[str] = set()
        self.crawled_count = 0

    def _is_internal(self, url: str) -> bool:
        """Checks if a URL belongs to the same domain and is part of the base path."""
        parsed_url = urlparse(url)
        same_domain = parsed_url.netloc == self.parsed_base.netloc
        # Ensure it starts with the base path to prevent climbing up to parent directories
        starts_with_path = parsed_url.path.startswith(self.parsed_base.path)
        return same_domain and starts_with_path

    async def crawl(self, output_filename: str) -> Path:
        """Executes the crawler recursively.

        Args:
            output_filename: Output filename to save inside the raw/ folder.
                             Saves as Markdown if it ends with .md, otherwise HTML.

        Returns:
            Path: Absolute path to the cached combined document.
        """
        logger.info(
            f"[Crawl4AI] Starting robust crawl: base_url={self.base_url}, max_depth={self.max_depth}"
        )

        queue = [(self.base_url, 0)]  # Queue of (url, current_depth)
        all_contents: List[str] = []
        is_markdown = output_filename.endswith(".md")

        async with AsyncWebCrawler() as crawler:
            while queue and self.crawled_count < self.max_pages:
                url, depth = queue.pop(0)

                # Strip anchor tags and trailing slashes to normalize URL
                url_clean = url.split("#")[0].rstrip("/")
                if not url_clean:
                    continue

                if url_clean in self.visited_urls:
                    continue

                self.visited_urls.add(url_clean)
                self.crawled_count += 1

                logger.info(
                    f"[Crawl4AI] Crawling ({self.crawled_count}/{self.max_pages}): {url_clean} at depth {depth}"
                )

                try:
                    # Respectful rate limiting
                    if self.crawled_count > 1:
                        await asyncio.sleep(self.politeness_delay)

                    # Trigger crawl4ai extraction
                    result = await crawler.arun(
                        url=url_clean,
                        bypass_cache=True,
                    )

                    if not result.success:
                        logger.warning(
                            f"[Crawl4AI] Failed to fetch: {url_clean} - Error: {result.error_message}"
                        )
                        continue

                    # Select requested format
                    content = result.markdown if is_markdown else result.html
                    if content:
                        header = f"\n\n<!-- PAGE_URL: {url_clean} -->\n\n"
                        all_contents.append(header + content)

                    # If not reached max depth, discover child links
                    if depth < self.max_depth:
                        soup = BeautifulSoup(result.html, "html.parser")
                        for a in soup.find_all("a", href=True):
                            href = a["href"]
                            full_url = urljoin(url_clean, href)
                            clean_full_url = full_url.split("#")[0].rstrip("/")

                            if (
                                self._is_internal(clean_full_url)
                                and clean_full_url not in self.visited_urls
                            ):
                                queue.append((clean_full_url, depth + 1))

                except Exception as e:
                    logger.error(f"[Crawl4AI] Error crawling {url_clean}: {e}")

        # Combine all fetched page contents into a single raw file
        raw_dir = settings.raw_data_dir
        cache_path = raw_dir / output_filename

        combined_content = "\n\n".join(all_contents)
        cache_path.write_text(combined_content, encoding="utf-8")

        logger.info(
            f"[Crawl4AI] Crawl complete. Wrote {len(all_contents)} pages to {cache_path}"
        )
        return cache_path
