"""
CLI entry point for News Hive.

Commands:
  source add <url>              Add a blog index URL to monitor (auto-seeds prior-day HTML)
  source list                   List all monitored sources
  source remove <url>           Remove a source

  collect [--date YYYYMMDD]     Fetch index pages, compute delta, download new articles
  process [--date YYYYMMDD]     Run AI extraction on downloaded articles
  run     [--date YYYYMMDD]     End-to-end: collect + process

Global options:
  --no-color                    Disable ANSI color in log output
  --debug                       Enable DEBUG-level log output
"""
import asyncio
from pathlib import Path
from datetime import datetime, timezone

import click

import newshive.log as log_module
from newshive.log import ColorLogger, set_level, set_color, DEBUG, INFO
from newshive.metadata_manager import MetadataManager
from newshive.storage import StorageManager
from newshive.task_orchestrator import run_collection_pipeline, run_extraction_pipeline

DEFAULT_DB_PATH    = Path("brain/page_index.db")
DEFAULT_DATA_DIR   = Path("data")

# CLI-level logger
log = ColorLogger("cli")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


# ─────────────────────────────────────────────────────────────────────────────
# Root group with global options
# ─────────────────────────────────────────────────────────────────────────────

@click.group()
@click.option("--no-color", is_flag=True, default=False, help="Disable ANSI color output.")
@click.option("--debug",    is_flag=True, default=False, help="Enable DEBUG log level.")
@click.option("--db-path",  type=click.Path(path_type=Path), default=DEFAULT_DB_PATH, show_default=True)
@click.option("--data-dir", type=click.Path(path_type=Path), default=DEFAULT_DATA_DIR, show_default=True)
@click.pass_context
def cli(ctx, no_color, debug, db_path, data_dir):
    """News Hive — Blog Monitor Pipeline"""
    set_color(not no_color)
    set_level(DEBUG if debug else INFO)

    ctx.ensure_object(dict)
    ctx.obj["db_path"]  = db_path
    ctx.obj["data_dir"] = data_dir


# ─────────────────────────────────────────────────────────────────────────────
# source commands
# ─────────────────────────────────────────────────────────────────────────────

@cli.group()
def source():
    """Manage blog index URLs to monitor."""
    pass


@source.command("add")
@click.argument("url")
@click.option("--label", default="", help="Optional human-readable label.")
@click.pass_context
def source_add(ctx, url, label):
    """Add a blog index URL. Auto-seeds a prior-day empty HTML baseline."""
    log.debug("→ source add start")
    db      = MetadataManager(ctx.obj["db_path"])
    storage = StorageManager(ctx.obj["data_dir"])

    added = db.add_blog_source(url, label=label)
    if not added:
        log.warning(f"Source already exists: {url}")
        return

    # Create empty prior-day seed so first collect has a baseline to diff against
    seed_path = storage.seed_empty_index(url)
    log.success(f"Added source: {url}")
    log.info(f"Prior-day seed created: {seed_path}")
    log.debug("← source add done")


@source.command("list")
@click.pass_context
def source_list(ctx):
    """List all monitored blog index URLs."""
    db = MetadataManager(ctx.obj["db_path"])
    sources = db.get_blog_sources()
    if not sources:
        log.info("No sources registered yet. Use: source add <url>")
        return
    log.info(f"Registered sources ({len(sources)}):")
    for s in sources:
        click.echo(f"  {s['url']}  ({s.get('label', '')})")


@source.command("remove")
@click.argument("url")
@click.pass_context
def source_remove(ctx, url):
    """Remove a blog index URL from monitoring."""
    db = MetadataManager(ctx.obj["db_path"])
    removed = db.remove_blog_source(url)
    if removed:
        log.success(f"Removed source: {url}")
    else:
        log.warning(f"Source not found: {url}")


# ─────────────────────────────────────────────────────────────────────────────
# collect command
# ─────────────────────────────────────────────────────────────────────────────

@cli.command("collect")
@click.option("--date",         default=None,  help="Target date (YYYYMMDD). Defaults to today.")
@click.option("--max-lookback", default=10,    show_default=True, help="Days to look back for prior snapshot.")
@click.option("--source-concurrency", default=4, show_default=True, help="Max parallel source fetches.")
@click.option("--article-concurrency", default=5, show_default=True, help="Max parallel article downloads.")
@click.pass_context
def collect(ctx, date, max_lookback, source_concurrency, article_concurrency):
    """
    Fetch blog index pages, compute new article deltas, and download new articles.
    Saves to: blog_index_html/YYYYMMDD/ and article_html/YYYYMMDD/
    """
    date = date or _today()
    log.info(f"Starting collection for date={date}")
    db      = MetadataManager(ctx.obj["db_path"])
    storage = StorageManager(ctx.obj["data_dir"])

    saved = asyncio.run(run_collection_pipeline(
        db=db,
        storage=storage,
        date=date,
        max_lookback=max_lookback,
        source_concurrency=source_concurrency,
        article_concurrency=article_concurrency,
    ))
    log.success(f"Collection done: {len(saved)} new articles downloaded")


# ─────────────────────────────────────────────────────────────────────────────
# process command
# ─────────────────────────────────────────────────────────────────────────────

@cli.command("process")
@click.option("--date",        default=None,         help="Target date (YYYYMMDD). Defaults to today.")
@click.option("--model",       default="gemma3:1b",  show_default=True, help="Ollama model name.")
@click.option("--concurrency", default=3,            show_default=True, help="Max parallel extractions.")
@click.pass_context
def process(ctx, date, model, concurrency):
    """
    Run AI extraction on downloaded articles.
    Saves summaries to: extracted_articles/YYYYMMDD/
    """
    date = date or _today()
    log.info(f"Starting extraction for date={date}, model={model}")
    db      = MetadataManager(ctx.obj["db_path"])
    storage = StorageManager(ctx.obj["data_dir"])

    count = asyncio.run(run_extraction_pipeline(
        db=db,
        storage=storage,
        date=date,
        model=model,
        concurrency=concurrency,
    ))
    log.success(f"Extraction done: {count} articles extracted")


# ─────────────────────────────────────────────────────────────────────────────
# run command (end-to-end)
# ─────────────────────────────────────────────────────────────────────────────

@cli.command("run")
@click.option("--date",        default=None,         help="Target date (YYYYMMDD). Defaults to today.")
@click.option("--model",       default="gemma3:1b",  show_default=True, help="Ollama model name.")
@click.option("--max-lookback",default=10,           show_default=True, help="Days to look back for prior snapshot.")
@click.pass_context
def run_pipeline(ctx, date, model, max_lookback):
    """
    End-to-end pipeline: collect new articles then run AI extraction.
    """
    date = date or _today()
    log.info(f"Starting end-to-end pipeline for date={date}")
    db      = MetadataManager(ctx.obj["db_path"])
    storage = StorageManager(ctx.obj["data_dir"])

    async def _run():
        saved = await run_collection_pipeline(
            db=db, storage=storage, date=date, max_lookback=max_lookback
        )
        log.info(f"Collection phase done: {len(saved)} new articles")
        count = await run_extraction_pipeline(
            db=db, storage=storage, date=date, model=model
        )
        return saved, count

    saved, count = asyncio.run(_run())
    log.success(f"Pipeline complete: {len(saved)} articles collected, {count} extracted")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
