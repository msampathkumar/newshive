"""
Tests for the updated DataManager — blog_sources and blog_articles tables.
"""
import pytest
import sqlite_utils
from ai_news_summarizer.database import DataManager, STATUS_DOWNLOADED, STATUS_EXTRACTED


@pytest.fixture
def db(tmp_path):
    return DataManager(db_path=tmp_path / "test.db")


# ── Schema ────────────────────────────────────────────────────────────────────

def test_tables_created(db, tmp_path):
    raw = sqlite_utils.Database(tmp_path / "test.db")
    assert "blog_sources" in raw.table_names()
    assert "blog_articles" in raw.table_names()


# ── blog_sources ──────────────────────────────────────────────────────────────

def test_add_blog_source(db):
    result = db.add_blog_source("https://example.com/blog", label="Example Blog")
    assert result is True
    sources = db.get_blog_sources()
    assert len(sources) == 1
    assert sources[0]["url"] == "https://example.com/blog"
    assert sources[0]["label"] == "Example Blog"


def test_add_blog_source_duplicate(db):
    db.add_blog_source("https://example.com/blog")
    result = db.add_blog_source("https://example.com/blog")
    assert result is False
    assert len(db.get_blog_sources()) == 1


def test_has_blog_source(db):
    assert not db.has_blog_source("https://example.com/blog")
    db.add_blog_source("https://example.com/blog")
    assert db.has_blog_source("https://example.com/blog")


def test_remove_blog_source(db):
    db.add_blog_source("https://example.com/blog")
    result = db.remove_blog_source("https://example.com/blog")
    assert result is True
    assert len(db.get_blog_sources()) == 0


def test_remove_nonexistent_source(db):
    result = db.remove_blog_source("https://does-not-exist.com")
    assert result is False


# ── blog_articles ─────────────────────────────────────────────────────────────

def test_register_article(db):
    db.add_blog_source("https://example.com/blog")
    db.register_article(
        "https://example.com/blog/post-1",
        source_url="https://example.com/blog",
    )
    assert db.is_article_registered("https://example.com/blog/post-1")


def test_is_article_registered_false(db):
    assert not db.is_article_registered("https://example.com/blog/unknown")


def test_update_article_status(db):
    db.add_blog_source("https://example.com/blog")
    db.register_article("https://example.com/blog/post-1", source_url="https://example.com/blog")
    db.update_article_status("https://example.com/blog/post-1", STATUS_EXTRACTED)

    pending = db.get_pending_extraction()
    urls = [r["url"] for r in pending]
    assert "https://example.com/blog/post-1" not in urls


def test_get_pending_extraction(db):
    db.add_blog_source("https://example.com/blog")
    db.register_article("https://example.com/blog/post-1", source_url="https://example.com/blog", status=STATUS_DOWNLOADED)
    db.register_article("https://example.com/blog/post-2", source_url="https://example.com/blog", status=STATUS_EXTRACTED)

    pending = db.get_pending_extraction()
    urls = [r["url"] for r in pending]
    assert "https://example.com/blog/post-1" in urls
    assert "https://example.com/blog/post-2" not in urls


def test_register_article_idempotent(db):
    db.add_blog_source("https://example.com/blog")
    db.register_article("https://example.com/blog/post-1", source_url="https://example.com/blog")
    db.register_article("https://example.com/blog/post-1", source_url="https://example.com/blog")
    assert db.is_article_registered("https://example.com/blog/post-1")
