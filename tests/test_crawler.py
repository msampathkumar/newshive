"""
Tests for BlogCrawler — link extraction, delta computation,
domain filtering, and fallback to older folder.
"""
import pytest
from unittest.mock import MagicMock, patch
from ai_news_summarizer.crawler import BlogCrawler


SAMPLE_HTML = """
<html>
<body>
  <nav>
    <a href="/blog/post-1">Post 1</a>
    <a href="/blog/post-2">Post 2</a>
    <a href="https://other.com/post">External</a>
    <a href="/about">About Page</a>
  </nav>
</body>
</html>
"""

BASE_URL = "https://example.com/blog"


@pytest.fixture
def storage_mock(tmp_path):
    """Minimal StorageManager mock."""
    m = MagicMock()
    m.find_most_recent_index_date.return_value = None
    return m


@pytest.fixture
def crawler(storage_mock):
    return BlogCrawler(storage=storage_mock)


# ── extract_child_urls ──────────────────────────────────────────────────────

def test_extract_child_urls_returns_absolute_urls(crawler):
    urls = crawler.extract_child_urls(SAMPLE_HTML, BASE_URL)
    assert "https://example.com/blog/post-1" in urls
    assert "https://example.com/blog/post-2" in urls
    assert "https://other.com/post" in urls


def test_extract_child_urls_strips_fragments(crawler):
    html = '<html><body><a href="/blog/post-1#section">Link</a></body></html>'
    urls = crawler.extract_child_urls(html, BASE_URL)
    assert "https://example.com/blog/post-1" in urls
    # Fragment version should NOT be present
    assert not any("#" in u for u in urls)


def test_extract_child_urls_empty_html(crawler):
    urls = crawler.extract_child_urls("<html><body></body></html>", BASE_URL)
    assert urls == set()


# ── compute_delta ───────────────────────────────────────────────────────────

def test_compute_delta_returns_new_only(crawler):
    current = {"https://example.com/blog/1", "https://example.com/blog/2", "https://example.com/blog/3"}
    prior   = {"https://example.com/blog/1", "https://example.com/blog/2"}
    delta   = crawler.compute_delta(current, prior)
    assert delta == {"https://example.com/blog/3"}


def test_compute_delta_empty_prior(crawler):
    current = {"https://example.com/blog/1"}
    delta = crawler.compute_delta(current, set())
    assert delta == current


def test_compute_delta_no_new_urls(crawler):
    current = {"https://example.com/blog/1"}
    delta = crawler.compute_delta(current, current)
    assert delta == set()


# ── filter_same_domain ───────────────────────────────────────────────────────

def test_filter_same_domain_keeps_sub_path(crawler):
    urls = {
        "https://example.com/blog/post-1",
        "https://example.com/blog/nested/post",
    }
    result = crawler.filter_same_domain("https://example.com/blog", urls)
    assert "https://example.com/blog/post-1" in result
    assert "https://example.com/blog/nested/post" in result


def test_filter_same_domain_drops_different_path(crawler):
    urls = {
        "https://example.com/about",
        "https://example.com/products/item",
    }
    result = crawler.filter_same_domain("https://example.com/blog", urls)
    assert len(result) == 0


def test_filter_same_domain_drops_external(crawler):
    urls = {"https://other.com/blog/post"}
    result = crawler.filter_same_domain("https://example.com/blog", urls)
    assert len(result) == 0


def test_filter_same_domain_excludes_index_itself(crawler):
    # The base URL itself should be excluded (not an article)
    urls = {"https://example.com/blog", "https://example.com/blog/post-1"}
    result = crawler.filter_same_domain("https://example.com/blog", urls)
    assert "https://example.com/blog" not in result
    assert "https://example.com/blog/post-1" in result


# ── get_prior_links fallback ─────────────────────────────────────────────────

def test_get_prior_links_falls_back_to_older_folder(storage_mock, crawler):
    """When day-1 is missing, should use whatever find_most_recent_index_date returns."""
    storage_mock.find_most_recent_index_date.return_value = "20260222"
    storage_mock.get_index_html.return_value = SAMPLE_HTML

    prior = crawler.get_prior_links("https://example.com/blog")
    # Should have found links from the fallback date
    assert len(prior) > 0
    storage_mock.get_index_html.assert_called_once_with("https://example.com/blog", "20260222")


def test_get_prior_links_returns_empty_when_no_prior(storage_mock, crawler):
    storage_mock.find_most_recent_index_date.return_value = None
    prior = crawler.get_prior_links("https://example.com/blog")
    assert prior == set()
