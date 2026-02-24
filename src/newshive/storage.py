"""
StorageManager — manages all local file storage for News Hive.

Folder layout (all under data/):
  blog_index_html/YYYYMMDD/<safe>.html  — daily snapshots of blog index pages
  article_html/YYYYMMDD/<safe>.html     — individual downloaded article pages
  extracted_articles/YYYYMMDD/<safe>.md — AI-extracted article content

A "safe" filename is derived from the URL by stripping the scheme and
replacing non-alphanumeric characters with hyphens.
"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from newshive.log import ColorLogger
from newshive.config import (
    DEFAULT_DATA_DIR,
    INDEX_HTML_DIR_NAME,
    ARTICLE_HTML_DIR_NAME,
    EXTRACTED_ARTICLES_DIR_NAME,
    MAX_LOOKBACK_DAYS,
)

log = ColorLogger("storage")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _date_minus(days: int) -> str:
    d = datetime.now(timezone.utc) - timedelta(days=days)
    return d.strftime("%Y%m%d")


def safe_filename(url: str) -> str:
    """Converts a URL into a safe, filesystem-friendly string."""
    url_no_scheme = re.sub(r"^https?://", "", url).rstrip("/")
    safe = re.sub(r"[^a-zA-Z0-9]", "-", url_no_scheme)
    return re.sub(r"-+", "-", safe)


# ─────────────────────────────────────────────────────────────────────────────
# StorageManager
# ─────────────────────────────────────────────────────────────────────────────

class StorageManager:
    """Manages the local file storage for the blog scraper pipeline."""

    def __init__(self, base_dir: Path | str = DEFAULT_DATA_DIR):
        self.base_dir = Path(base_dir)
        self.index_dir = self.base_dir / INDEX_HTML_DIR_NAME
        self.article_dir = self.base_dir / ARTICLE_HTML_DIR_NAME
        self.extracted_dir = self.base_dir / EXTRACTED_ARTICLES_DIR_NAME
        log.debug("→ StorageManager init: base_dir=%s", )

    def _ensure(self, path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ── Blog index page snapshots ─────────────────────────────────────────

    def save_index_html(self, url: str, html: str, date: str | None = None) -> Path:
        """Save a blog index page snapshot for a given date (default: today)."""
        log.debug(f"→ save_index_html start: url={url}, date={date}")
        date = date or _today()
        folder = self._ensure(self.index_dir / date)
        path = folder / f"{safe_filename(url)}.html"
        path.write_text(html, encoding="utf-8")
        log.debug(f"← save_index_html done: {path}")
        return path

    def get_index_html(self, url: str, date: str) -> str:
        """Read a saved blog index page snapshot."""
        log.debug(f"→ get_index_html: url={url}, date={date}")
        path = self.index_dir / date / f"{safe_filename(url)}.html"
        return path.read_text(encoding="utf-8")

    def has_index_html(self, url: str, date: str) -> bool:
        path = self.index_dir / date / f"{safe_filename(url)}.html"
        return path.exists()

    def seed_empty_index(self, url: str, date: str | None = None) -> Path:
        """
        Write an empty placeholder HTML for the given date (defaults to yesterday).
        Called automatically when a new source URL is added so that the first
        real fetch always has a prior-day baseline to diff against.
        """
        log.debug(f"→ seed_empty_index: url={url}, date={date}")
        date = date or _date_minus(1)
        folder = self._ensure(self.index_dir / date)
        path = folder / f"{safe_filename(url)}.html"
        if not path.exists():
            path.write_text("", encoding="utf-8")
            log.info(f"Seeded empty index baseline → {path}")
        else:
            log.debug(f"← seed_empty_index: baseline already exists, skipping")
        return path

    def find_most_recent_index_date(self, url: str, max_lookback: int = MAX_LOOKBACK_DAYS) -> str | None:
        """
        Walk back from today-1 up to max_lookback days to find the most recent
        date folder that contains a saved index HTML for url.
        Returns the YYYYMMDD string, or None if nothing found.
        """
        log.debug(f"→ find_most_recent_index_date: url={url}, max_lookback={max_lookback}")
        for days_back in range(1, max_lookback + 1):
            date = _date_minus(days_back)
            if self.has_index_html(url, date):
                log.debug(f"← found prior index at day -{days_back}: {date}")
                return date
        log.warning(f"No prior index found for {url} (looked back {max_lookback} days)")
        return None

    # ── Individual article downloads ──────────────────────────────────────

    def save_article_html(self, url: str, html: str, date: str | None = None) -> Path:
        """Save a downloaded article's HTML."""
        log.debug(f"→ save_article_html start: url={url}")
        date = date or _today()
        folder = self._ensure(self.article_dir / date)
        path = folder / f"{safe_filename(url)}.html"
        path.write_text(html, encoding="utf-8")
        log.debug(f"← save_article_html done: {path}")
        return path

    def get_article_html(self, url: str, date: str) -> str:
        """Read a saved article HTML."""
        path = self.article_dir / date / f"{safe_filename(url)}.html"
        return path.read_text(encoding="utf-8")

    def has_article_html(self, url: str, date: str) -> bool:
        path = self.article_dir / date / f"{safe_filename(url)}.html"
        return path.exists()

    def list_article_urls_for_date(self, date: str) -> list[str]:
        """
        Return safe filenames (stems) of all articles downloaded for a date.
        These can be mapped back to storage paths but not to original URLs.
        Returns empty list if folder doesn't exist.
        """
        folder = self.article_dir / date
        if not folder.exists():
            return []
        return [p.stem for p in folder.glob("*.html")]

    # ── AI-extracted article content ──────────────────────────────────────

    def save_extracted_article(self, url: str, text: str, date: str | None = None) -> Path:
        """Save AI-extracted article content as Markdown."""
        log.debug(f"→ save_extracted_article start: url={url}")
        date = date or _today()
        folder = self._ensure(self.extracted_dir / date)
        path = folder / f"{safe_filename(url)}.md"
        path.write_text(text, encoding="utf-8")
        log.debug(f"← save_extracted_article done: {path}")
        return path

    def get_extracted_article(self, url: str, date: str) -> str:
        """Read an extracted article Markdown file."""
        path = self.extracted_dir / date / f"{safe_filename(url)}.md"
        return path.read_text(encoding="utf-8")

    def has_extracted_article(self, url: str, date: str) -> bool:
        path = self.extracted_dir / date / f"{safe_filename(url)}.md"
        return path.exists()
