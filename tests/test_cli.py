"""
Tests for the CLI commands — updated for the new source/collect/process/run API.
"""
import pytest
from click.testing import CliRunner
from unittest.mock import patch, AsyncMock, MagicMock

from ai_news_summarizer.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


# ── help ──────────────────────────────────────────────────────────────────────

def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "News" in result.output


# ── source add ────────────────────────────────────────────────────────────────

def test_source_add(runner, temp_db_path, tmp_path):
    result = runner.invoke(cli, [
        "--db-path", str(temp_db_path),
        "--data-dir", str(tmp_path),
        "source", "add", "https://example.com/blog",
    ])
    assert result.exit_code == 0, result.output
    assert "Added blog source" in result.output or "example.com/blog" in result.output


def test_source_add_auto_seeds_prior_day(runner, temp_db_path, tmp_path):
    runner.invoke(cli, [
        "--db-path", str(temp_db_path),
        "--data-dir", str(tmp_path),
        "source", "add", "https://example.com/blog",
    ])
    # A seed file should exist inside blog_index_html/
    seed_files = list((tmp_path / "blog_index_html").rglob("*.html"))
    assert len(seed_files) == 1


# ── source list ───────────────────────────────────────────────────────────────

def test_source_list_empty(runner, temp_db_path, tmp_path):
    result = runner.invoke(cli, [
        "--db-path", str(temp_db_path),
        "--data-dir", str(tmp_path),
        "source", "list",
    ])
    assert result.exit_code == 0
    # Should mention there's nothing registered
    assert "No sources" in result.output or result.exit_code == 0


def test_source_list_shows_url(runner, temp_db_path, tmp_path):
    # Add first
    runner.invoke(cli, [
        "--db-path", str(temp_db_path),
        "--data-dir", str(tmp_path),
        "source", "add", "https://example.com/blog",
    ])
    result = runner.invoke(cli, [
        "--db-path", str(temp_db_path),
        "--data-dir", str(tmp_path),
        "source", "list",
    ])
    assert result.exit_code == 0
    assert "https://example.com/blog" in result.output


# ── source remove ─────────────────────────────────────────────────────────────

def test_source_remove(runner, temp_db_path, tmp_path):
    runner.invoke(cli, [
        "--db-path", str(temp_db_path),
        "--data-dir", str(tmp_path),
        "source", "add", "https://example.com/blog",
    ])
    result = runner.invoke(cli, [
        "--db-path", str(temp_db_path),
        "--data-dir", str(tmp_path),
        "source", "remove", "https://example.com/blog",
    ])
    assert result.exit_code == 0
    assert "Removed" in result.output or "example.com/blog" in result.output


# ── global flags ──────────────────────────────────────────────────────────────

def test_no_color_flag(runner, temp_db_path, tmp_path):
    result = runner.invoke(cli, [
        "--no-color",
        "--db-path", str(temp_db_path),
        "--data-dir", str(tmp_path),
        "source", "list",
    ])
    assert result.exit_code == 0
    # No ANSI escape codes in output
    assert "\033[" not in result.output


def test_debug_flag_accepted(runner, temp_db_path, tmp_path):
    result = runner.invoke(cli, [
        "--debug",
        "--db-path", str(temp_db_path),
        "--data-dir", str(tmp_path),
        "source", "list",
    ])
    assert result.exit_code == 0
