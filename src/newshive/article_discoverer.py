"""
ArticleDiscoverer — fetches blog index pages, extracts article links, computes
deltas against the prior day's saved snapshot, and downloads new articles.

Flow per source URL:
  1. fetch_index_page()        → save to blog_index_html/YYYYMMDD/
  2. extract_child_urls()      → BeautifulSoup <a href> parsing
  3. find_most_recent_prior()  → find prior-day HTML (up to 10 days back)
  4. compute_delta()           → new links not in prior snapshot
  5. filter_same_domain()      → keep only same-domain sub-path URLs
  6. download_article()        → save to article_html/YYYYMMDD/
"""
import asyncio
from urllib.parse import urljoin, urlparse, urldefrag
import re

import httpx
from bs4 import BeautifulSoup

from newshive.log import ColorLogger
from newshive.storage import StorageManager, safe_filename
from newshive.config import URL_IGNORE_PATTERNS, PAGE_TIMEOUT_SECONDS # NEW

log = ColorLogger("article_discoverer")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


class ArticleDiscoverer:
    """
    Responsible for:
    - Fetching blog index pages and saving snapshots
    - Extracting child article URLs via BeautifulSoup
    - Computing delta URLs vs the prior day's snapshot
    - Filtering to same-domain sub-path URLs
    - Downloading individual articles and saving them
    """

    def __init__(self, storage: StorageManager, timeout: int = PAGE_TIMEOUT_SECONDS):
        self.storage = storage
        self.timeout = timeout
        log.debug("→ ArticleDiscoverer init")

    # ── Fetch & Save Index ────────────────────────────────────────────────────

    async def fetch_index_page(self, url: str, date: str) -> str:
        """
        HTTP GET the blog index page, save it, and return the raw HTML.
        Raises httpx.HTTPError on network/HTTP failures.
        """
        log.debug(f"→ fetch_index_page: url={url}, date={date}")
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=_HEADERS)
            response.raise_for_status()
            raw_html = response.text

        path = self.storage.save_index_html(url, raw_html, date)
        log.info(f"Fetched index page → {path.name}")
        log.debug(f"← fetch_index_page done: {len(raw_html)} bytes")
        return raw_html

    # ── Link Extraction ───────────────────────────────────────────────────────

    def extract_child_urls(self, html: str, base_url: str) -> set[str]:
        """
        Parse <a href> tags from HTML using BeautifulSoup.
        Resolves relative URLs to absolute using base_url.
        Strips URL fragments (#).
        Returns a set of clean http(s) URLs.
        """
        log.debug(f"→ extract_child_urls: base_url={base_url}")
        soup = BeautifulSoup(html, "html.parser")
        found: set[str] = set()

        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            absolute = urljoin(base_url, href)
            clean, _ = urldefrag(absolute)
            if clean.startswith("http://") or clean.startswith("https://"):
                found.add(clean)

        log.debug(f"← extract_child_urls: found {len(found)} URLs")
        return found

    def _filter_ignored_urls(self, urls: set[str]) -> set[str]:
        """
        Filters out URLs that match any pattern in URL_IGNORE_PATTERNS.
        """
        log.debug(f"→ _filter_ignored_urls: candidates={len(urls)}")
        filtered_urls = set()
        for url in urls:
            ignored = False
            for pattern in URL_IGNORE_PATTERNS:
                if re.match(pattern, url):
                    ignored = True
                    log.debug(f"Ignoring URL '{url}' due to pattern '{pattern}'")
                    break
            if not ignored:
                filtered_urls.add(url)
        log.debug(f"← _filter_ignored_urls: kept {len(filtered_urls)} / {len(urls)}")
        return filtered_urls

    # ── Delta Computation ─────────────────────────────────────────────────────

    def compute_delta(
        self, current_links: set[str], prior_links: set[str]
    ) -> set[str]:
        """Return URLs in current_links that are not in prior_links."""
        log.debug(f"→ compute_delta: current={len(current_links)}, prior={len(prior_links)}")
        delta = current_links - prior_links
        log.debug(f"← compute_delta: {len(delta)} new URLs")
        return delta

    def get_prior_links(self, source_url: str, max_lookback: int = 10) -> set[str]:
        """
        Find the most recent prior-day snapshot and extract its links.
        Returns empty set if no prior snapshot exists (e.g., first run).
        """
        log.debug(f"→ get_prior_links: source_url={source_url}")
        prior_date = self.storage.find_most_recent_index_date(source_url, max_lookback)
        if prior_date is None:
            log.info(f"No prior snapshot found for {source_url} — treating all links as new")
            return set()
        prior_html = self.storage.get_index_html(source_url, prior_date)
        prior_links = self.extract_child_urls(prior_html, source_url)
        log.debug(f"← get_prior_links: {len(prior_links)} links from prior date {prior_date}")
        return prior_links

    # ── Domain Filtering ──────────────────────────────────────────────────────

    def filter_same_domain(self, base_url: str, urls: set[str]) -> set[str]:
        """
        Keep only URLs that share the same domain AND are under the same path prefix.

        Example:
          base_url = "https://example.com/blog"
          "https://example.com/blog/hello.html"  → KEPT
          "https://example.com/about"             → DROPPED (different path)
          "https://other.com/blog/post"           → DROPPED (different domain)
        """
        log.debug(f"→ filter_same_domain: base={base_url}, candidates={len(urls)}")
        parsed_base = urlparse(base_url)
        base_netloc = parsed_base.netloc.lower()
        base_path   = parsed_base.path.rstrip("/")

        kept: set[str] = set()
        for url in urls:
            p = urlparse(url)
            if (
                p.netloc.lower() == base_netloc
                and p.path.startswith(base_path)
                and p.path != base_path  # exclude the index page itself
            ):
                kept.add(url)

        log.debug(f"← filter_same_domain: kept {len(kept)} / {len(urls)}")
        return kept

    # ── Article Download ──────────────────────────────────────────────────────

    async def download_article(self, url: str, date: str) -> str | None:
        """
        Download a single article page and save it.
        Returns raw HTML on success, None on failure (logs the error).
        """
        log.debug(f"→ download_article: url={url}")
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True
            ) as client:
                response = await client.get(url, headers=_HEADERS)
                response.raise_for_status()
                html = response.text

            path = self.storage.save_article_html(url, html, date)
            log.debug(f"← download_article done: {path.name}")
            return html

        except httpx.HTTPStatusError as e:
            log.error(f"HTTP {e.response.status_code} downloading article: {url}")
            return None
        except httpx.HTTPError as e:
            log.error(f"Network error downloading article {url}: {e}")
            return None

    async def download_articles_batch(
        self, urls: list[str], date: str, concurrency: int = 5
    ) -> dict[str, str | None]:
        """
        Download multiple articles in parallel using asyncio.gather,
        with a semaphore to cap concurrent connections.
        Returns dict mapping url → html (or None on failure).
        """
        log.debug(f"→ download_articles_batch: {len(urls)} articles, concurrency={concurrency}")
        sem = asyncio.Semaphore(concurrency)

        async def _bounded(url: str) -> tuple[str, str | None]:
            async with sem:
                html = await self.download_article(url, date)
                return url, html

        results = await asyncio.gather(*[_bounded(u) for u in urls])
        ok = sum(1 for _, h in results if h is not None)
        log.debug(f"← download_articles_batch done: {ok}/{len(urls)} succeeded")
        return dict(results)

    # ── Full Collection for One Source ────────────────────────────────────────

    async def collect_source(
        self,
        source_url: str,
        date: str,
        registered_check,   # callable(url: str) -> bool
        max_lookback: int = 10,
    ) -> list[str]:
        """
        Full pipeline for one source URL:
          1. Fetch & save index page
          2. Extract child URLs
          3. Compute delta vs prior day
          4. Filter to same-domain/sub-path
          5. Remove already-registered URLs
          Returns list of net-new article URLs (not yet downloaded).
        """
        log.debug(f"→ collect_source: {source_url}")

        # Step 1: Fetch index
        try:
            html = await self.fetch_index_page(source_url, date)
        except httpx.HTTPError as e:
            log.error(f"Failed to fetch index {source_url}: {e}")
            return []

        # Step 2: Extract links
        current_links = self.extract_child_urls(html, source_url)

        # Step 2.5: Filter out ignored URLs
        current_links = self._filter_ignored_urls(current_links)

        # Step 3: Delta vs prior day
        prior_links = self.get_prior_links(source_url, max_lookback)
        delta = self.compute_delta(current_links, prior_links)

        # Step 4: Filter same domain
        candidates = self.filter_same_domain(source_url, delta)

        # Step 5: Remove already-registered
        new_urls = [u for u in candidates if not registered_check(u)]

        log.info(
            f"Source {source_url}: "
            f"{len(current_links)} links found, "
            f"{len(delta)} delta, "
            f"{len(candidates)} same-domain, "
            f"{len(new_urls)} new articles"
        )
        log.debug(f"← collect_source done: {len(new_urls)} new")
        return new_urls
