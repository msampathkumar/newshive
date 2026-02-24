"""
Tests for the updated StorageManager with date-partitioned paths,
seed_empty_index, and find_most_recent_index_date fallback logic.
"""
import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from ai_news_summarizer.storage import StorageManager, safe_filename


def _fmt(d: datetime) -> str:
    return d.strftime("%Y%m%d")


@pytest.fixture
def storage(tmp_path):
    return StorageManager(base_dir=tmp_path)


# ── safe_filename ─────────────────────────────────────────────────────────────

def test_safe_filename_strips_scheme():
    assert "example-com-blog" == safe_filename("https://example.com/blog")


def test_safe_filename_no_trailing_slash():
    name = safe_filename("https://example.com/blog/")
    assert not name.endswith("-")


# ── save / get / has index HTML ───────────────────────────────────────────────

def test_save_index_html_creates_file(storage):
    path = storage.save_index_html("https://example.com/blog", "<html/>", date="20260224")
    assert path.exists()
    assert path.read_text() == "<html/>"


def test_has_index_html_true(storage):
    storage.save_index_html("https://example.com/blog", "<html/>", date="20260224")
    assert storage.has_index_html("https://example.com/blog", "20260224")


def test_has_index_html_false(storage):
    assert not storage.has_index_html("https://example.com/blog", "20260224")


def test_get_index_html(storage):
    storage.save_index_html("https://example.com/blog", "<html>hello</html>", date="20260224")
    content = storage.get_index_html("https://example.com/blog", "20260224")
    assert "hello" in content


# ── seed_empty_index ─────────────────────────────────────────────────────────

def test_seed_empty_index_creates_file(storage):
    yesterday = _fmt(datetime.now(timezone.utc) - timedelta(days=1))
    path = storage.seed_empty_index("https://example.com/blog")
    assert path.exists()
    assert path.read_text() == ""
    assert yesterday in str(path)


def test_seed_empty_index_explicit_date(storage):
    path = storage.seed_empty_index("https://example.com/blog", date="20260101")
    assert path.exists()
    assert "20260101" in str(path)


def test_seed_empty_index_does_not_overwrite(storage):
    storage.save_index_html("https://example.com/blog", "<existing/>", date="20260101")
    storage.seed_empty_index("https://example.com/blog", date="20260101")
    # Should not have overwritten existing content
    assert storage.get_index_html("https://example.com/blog", "20260101") == "<existing/>"


# ── find_most_recent_index_date ───────────────────────────────────────────────

def test_finds_yesterday(storage):
    yesterday = _fmt(datetime.now(timezone.utc) - timedelta(days=1))
    storage.save_index_html("https://example.com/blog", "<html/>", date=yesterday)
    result = storage.find_most_recent_index_date("https://example.com/blog")
    assert result == yesterday


def test_fallback_to_older_date(storage):
    three_days_ago = _fmt(datetime.now(timezone.utc) - timedelta(days=3))
    storage.save_index_html("https://example.com/blog", "<html/>", date=three_days_ago)
    result = storage.find_most_recent_index_date("https://example.com/blog", max_lookback=10)
    assert result == three_days_ago


def test_returns_none_when_no_prior(storage):
    result = storage.find_most_recent_index_date("https://example.com/blog", max_lookback=3)
    assert result is None


# ── article_html ──────────────────────────────────────────────────────────────

def test_save_article_html(storage):
    path = storage.save_article_html("https://example.com/blog/post-1", "<article/>", date="20260224")
    assert path.exists()
    assert "article_html" in str(path)
    assert "20260224" in str(path)


def test_has_article_html(storage):
    storage.save_article_html("https://example.com/blog/post-1", "<article/>", date="20260224")
    assert storage.has_article_html("https://example.com/blog/post-1", "20260224")
    assert not storage.has_article_html("https://example.com/blog/post-2", "20260224")


# ── extracted_articles ────────────────────────────────────────────────────────

def test_save_extracted_article(storage):
    path = storage.save_extracted_article("https://example.com/blog/post-1", "# Summary", date="20260224")
    assert path.exists()
    assert path.suffix == ".md"
    assert "extracted_articles" in str(path)


def test_get_extracted_article(storage):
    storage.save_extracted_article("https://example.com/blog/post-1", "# My Summary", date="20260224")
    text = storage.get_extracted_article("https://example.com/blog/post-1", "20260224")
    assert "My Summary" in text
