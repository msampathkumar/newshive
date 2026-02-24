"""
MetadataManager — SQLite database layer for News Hive.

Tables:
  blog_sources   — the blog index pages to monitor (seed URLs)
  blog_articles  — tracks discovered + downloaded + extracted articles

No FK constraints: articles are discovered dynamically and don't need
to be pre-registered before being downloaded.
"""
import sqlite_utils
from pathlib import Path
from datetime import datetime, timezone

from newshive.log import ColorLogger
from newshive.config import SOURCES_TABLE_NAME, ARTICLES_TABLE_NAME

log = ColorLogger("metadata_manager")

# Article statuses
STATUS_DOWNLOADED  = "downloaded"
STATUS_EXTRACTED   = "extracted"
STATUS_ERROR_FETCH = "error_fetch"
STATUS_ERROR_LLM   = "error_llm"
STATUS_SKIPPED     = "skipped"


class MetadataManager:
    """Manages the SQLite database index for the News Hive pipeline."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        log.debug(f"→ MetadataManager init: db_path={self.db_path}")
        self._init_db()
        log.debug("← MetadataManager init done")

    # ── Schema ───────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Initialize tables if they do not already exist."""
        db = sqlite_utils.Database(self.db_path)

        if SOURCES_TABLE_NAME not in db.table_names():
            db[SOURCES_TABLE_NAME].create({
                "url":      str,
                "label":    str,
                "added_at": str,
            }, pk="url")
            log.debug(f"Created table: {SOURCES_TABLE_NAME}")

        if ARTICLES_TABLE_NAME not in db.table_names():
            db[ARTICLES_TABLE_NAME].create({
                "url":          str,
                "source_url":   str,
                "status":       str,
                "scraped_at":   str,
                "extracted_at": str,
                "published_date": str,  # NEW
                "github_links": str,    # NEW (store as JSON string)
            }, pk="url")
            log.debug(f"Created table: {ARTICLES_TABLE_NAME}")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Blog Sources ─────────────────────────────────────────────────────────

    def add_blog_source(self, url: str, label: str = "") -> bool:
        """
        Add a new blog index URL to monitor.
        Returns True if newly added, False if already existed.
        """
        log.debug(f"→ add_blog_source: url={url}")
        db = sqlite_utils.Database(self.db_path)
        try:
            db[SOURCES_TABLE_NAME].insert({
                "url":      url,
                "label":    label or url,
                "added_at": self._now(),
            })
            log.info(f"Added blog source: {url}")
            log.debug("← add_blog_source: inserted")
            return True
        except Exception:
            log.debug(f"← add_blog_source: already exists, skipped")
            return False

    def remove_blog_source(self, url: str) -> bool:
        """Remove a blog source. Returns True if it existed."""
        log.debug(f"→ remove_blog_source: url={url}")
        db = sqlite_utils.Database(self.db_path)
        try:
            db[SOURCES_TABLE_NAME].delete(url)
            log.info(f"Removed blog source: {url}")
            return True
        except Exception:
            log.warning(f"Attempted to remove non-existent source: {url}")
            return False

    def get_blog_sources(self) -> list[dict]:
        """Return all registered blog index URLs with metadata."""
        log.debug("→ get_blog_sources")
        db = sqlite_utils.Database(self.db_path)
        sources = [dict(row) for row in db[SOURCES_TABLE_NAME].rows]
        log.debug(f"← get_blog_sources: {len(sources)} sources")
        return sources

    def has_blog_source(self, url: str) -> bool:
        db = sqlite_utils.Database(self.db_path)
        try:
            db[SOURCES_TABLE_NAME].get(url)
            return True
        except Exception:
            return False

    # ── Blog Articles ─────────────────────────────────────────────────────────

    def is_article_registered(self, url: str) -> bool:
        """Check if an article URL is already tracked in blog_articles."""
        log.debug(f"→ is_article_registered: url={url}")
        db = sqlite_utils.Database(self.db_path)
        try:
            db[ARTICLES_TABLE_NAME].get(url)
            log.debug("← is_article_registered: True")
            return True
        except Exception:
            log.debug("← is_article_registered: False")
            return False

    def register_article(self, url: str, source_url: str, status: str = STATUS_DOWNLOADED, published_date: str | None = None, github_links: str | None = None) -> None:
        """Insert or update an article record."""
        log.debug(f"→ register_article: url={url}, status={status}")
        db = sqlite_utils.Database(self.db_path)
        now = self._now()
        db[ARTICLES_TABLE_NAME].upsert({
            "url":          url,
            "source_url":   source_url,
            "status":       status,
            "scraped_at":   now,
            "extracted_at": None,
            "published_date": published_date,
            "github_links": github_links,
        }, pk="url")
        log.debug("← register_article done")

    def update_article_status(self, url: str, status: str) -> None:
        """Update the status of an existing article."""
        log.debug(f"→ update_article_status: url={url}, status={status}")
        db = sqlite_utils.Database(self.db_path)
        update: dict = {"status": status}
        if status == STATUS_EXTRACTED:
            update["extracted_at"] = self._now()
        db[ARTICLES_TABLE_NAME].update(url, update)
        log.debug("← update_article_status done")

    def get_article_source_url(self, article_url: str) -> str | None:
        """Retrieve the source_url for a given article URL."""
        db = sqlite_utils.Database(self.db_path)
        row = db[ARTICLES_TABLE_NAME].get(article_url)
        if row:
            return row["source_url"]
        return None

    def get_pending_extraction(self, date: str | None = None) -> list[dict]:
        """
        Return articles with status 'downloaded' (i.e., ready for AI extraction).
        If date is provided, it's informational only — filtering is by status.
        """
        log.debug(f"→ get_pending_extraction: date={date}")
        db = sqlite_utils.Database(self.db_path)
        rows = [
            dict(r) for r in db[ARTICLES_TABLE_NAME].rows_where(
                "status = ?", [STATUS_DOWNLOADED]
            )
        ]
        log.debug(f"← get_pending_extraction: {len(rows)} pending")
        return rows

    def get_articles_for_date(self, date: str) -> list[dict]:
        """Return all articles registered on a given date (scraped_at LIKE YYYYMMDD%)."""
        log.debug(f"→ get_articles_for_date: date={date}")
        db = sqlite_utils.Database(self.db_path)
        # ISO timestamp starts with YYYY-MM-DD; convert YYYYMMDD → YYYY-MM-DD prefix
        date_prefix = f"{date[:4]}-{date[4:6]}-{date[6:8]}%"
        rows = [
            dict(r) for r in db[ARTICLES_TABLE_NAME].rows_where(
                "scraped_at LIKE ?", [date_prefix]
            )
        ]
        log.debug(f"← get_articles_for_date: {len(rows)} articles")
        return rows
