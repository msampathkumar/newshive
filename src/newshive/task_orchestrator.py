"""
TaskOrchestrator — asyncio orchestration for the AI News Summarizer.

Two main orchestrators:

1. run_collection_pipeline()
   For each source URL (in parallel):
     - Fetch index page
     - Extract + delta + filter
     - Download new articles
     - Register in database

2. run_extraction_pipeline()
   For each downloaded article (in parallel):
     - Run AI extraction (ContentProcessor)
     - Save to extracted_articles/YYYYMMDD/
"""
import asyncio
from datetime import datetime, timezone
import json

from newshive.log import ColorLogger
from newshive.storage import StorageManager
from newshive.metadata_manager import MetadataManager, STATUS_DOWNLOADED, STATUS_EXTRACTED, STATUS_ERROR_FETCH, STATUS_ERROR_LLM
from newshive.article_discoverer import ArticleDiscoverer
from newshive.content_processor import ContentProcessor
from newshive.config import PIPELINE_LOCK_FILE

log = ColorLogger("task_orchestrator")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


# ─────────────────────────────────────────────────────────────────────────────
# Collection Pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def _collect_one_source(
    source_url: str,
    date: str,
    discoverer: ArticleDiscoverer,
    db: MetadataManager,
    storage: StorageManager,
    max_lookback: int,
    article_concurrency: int,
) -> list[str]:
    """Handle collection for a single source URL."""
    if not PIPELINE_LOCK_FILE.exists():
        log.warning("Lock file removed. Stopping collection task.")
        return []

    log.debug(f"→ _collect_one_source: {source_url}")

    # Step 1-5: Discover new article URLs
    new_article_urls = await discoverer.collect_source(
        source_url=source_url,
        date=date,
        registered_check=db.is_article_registered,
        max_lookback=max_lookback,
    )

    if not new_article_urls:
        log.info(f"No new articles found for: {source_url}")
        return []

    # Check lock file again before starting downloads
    if not PIPELINE_LOCK_FILE.exists():
        log.warning("Lock file removed. Aborting article download.")
        return []

    # Step 6: Download articles in parallel (bounded)
    log.info(f"Downloading {len(new_article_urls)} new articles from {source_url} ...")
    download_results = await discoverer.download_articles_batch(
        new_article_urls, date, concurrency=article_concurrency
    )

    # Step 7: Register in database
    saved: list[str] = []
    for url, html in download_results.items():
        if not PIPELINE_LOCK_FILE.exists():
            log.warning("Lock file removed. Halting article registration.")
            break

        if html is not None:
            db.register_article(url, source_url=source_url, status=STATUS_DOWNLOADED)
            saved.append(url)
            log.debug(f"  Registered: {url}")
        else:
            db.register_article(url, source_url=source_url, status=STATUS_ERROR_FETCH)
            log.warning(f"  Failed to download: {url}")

    log.success(f"{source_url}: {len(saved)} articles saved")
    log.debug(f"← _collect_one_source done: {len(saved)} saved")
    return saved


async def run_collection_pipeline(
    db: MetadataManager,
    storage: StorageManager,
    date: str,
    max_lookback: int,
    source_concurrency: int,
    article_concurrency: int,
) -> list[str]:
    """
    Run the collection pipeline for all registered source URLs in parallel.

    Steps per source URL:
      1. Fetch index page → blog_index_html/YYYYMMDD/
      2. Extract child URLs (BeautifulSoup)
      3. Compute delta vs prior-day snapshot
      4. Filter same-domain sub-path URLs
      5. Remove already-registered articles
      6. Download new articles → article_html/YYYYMMDD/
      7. Register in blog_articles table

    Returns list of all newly downloaded article URLs.
    """
    log.debug("→ run_collection_pipeline start")
    sources = db.get_blog_sources()

    if not sources:
        log.warning("No blog sources registered. Use: newshive source add <url>")
        return []

    log.info(f"Collection pipeline: {len(sources)} sources, date={date}")
    discoverer = ArticleDiscoverer(storage)

    # Run all sources in parallel (bounded by semaphore)
    sem = asyncio.Semaphore(source_concurrency)

    async def _bounded(source: dict) -> list[str]:
        async with sem:
            if not PIPELINE_LOCK_FILE.exists():
                log.warning("Lock file removed. Skipping source.")
                return []
            return await _collect_one_source(
                source_url=source["url"],
                date=date,
                discoverer=discoverer,
                db=db,
                storage=storage,
                max_lookback=max_lookback,
                article_concurrency=article_concurrency,
            )

    results = await asyncio.gather(*[_bounded(s) for s in sources])
    all_saved = [url for batch in results for url in batch]

    log.success(f"Collection complete: {len(all_saved)} total new articles saved")
    log.debug("← run_collection_pipeline done")
    return all_saved


# ─────────────────────────────────────────────────────────────────────────────
# Extraction Pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def _extract_one_article(
    row: dict,
    date: str,
    storage: StorageManager,
    db: MetadataManager,
    processor: ContentProcessor,
) -> bool:
    """Run AI extraction for a single article."""
    if not PIPELINE_LOCK_FILE.exists():
        log.warning("Lock file removed. Skipping extraction task.")
        return False

    url = row["url"]
    log.debug(f"→ _extract_one_article: {url}")

    # Load saved article HTML
    html = storage.get_article_html(url, date)
    if not html:
        log.warning(f"Article HTML not found on disk (date={date}): {url}")
        db.update_article_status(url, STATUS_ERROR_FETCH) # Mark as error since HTML not found
        return False

    # Run AI processing (extraction + summarization)
    loop = asyncio.get_event_loop()
    try:
        processed_data = await loop.run_in_executor(None, processor.process_article, html, url, row["scraped_at"])
        summary        = processed_data.get("summary")
        extracted_text = processed_data.get("extracted_text")
        published_date = processed_data.get("published_date")
        github_links   = processed_data.get("github_links")
    except Exception as e:
        log.error(f"AI extraction failed for {url}: {e}")
        db.update_article_status(url, STATUS_ERROR_LLM)
        return False

    if not extracted_text:
        log.warning(f"No text extractable from article: {url}, skipping summarization.")
        db.update_article_status(url, STATUS_ERROR_LLM)
        return False

    if not summary:
        log.warning(f"No summary generated for article: {url}.")
        # Proceed with other data if summary is None, mark as extracted.

    # Save summary markdown
    storage.save_extracted_article(url, summary or extracted_text, date) # Save summary, or full text if no summary

    # Update metadata in DB
    db.register_article( # Using upsert capability of register_article
        url=url,
        source_url=db.get_article_source_url(url), # Need to retrieve source_url
        status=STATUS_EXTRACTED,
        published_date=published_date,
        github_links=json.dumps(github_links) if github_links else None,
    )
    log.debug(f"← _extract_one_article done: {url}")
    return True


async def run_extraction_pipeline(
    db: MetadataManager,
    storage: StorageManager,
    date: str,
    model: str,
    concurrency: int,
) -> int:
    """
    Run AI extraction for all articles with status 'downloaded'.

    Returns count of successfully extracted articles.
    """
    log.debug("→ run_extraction_pipeline start")
    pending = db.get_pending_extraction(date)

    if not pending:
        log.info("No articles pending extraction.")
        return 0

    log.info(f"Extraction pipeline: {len(pending)} articles, model={model}, date={date}")
    processor = ContentProcessor(model_name=model)

    sem = asyncio.Semaphore(concurrency)

    async def _bounded(row: dict) -> bool:
        async with sem:
            return await _extract_one_article(
                row=row,
                date=date,
                storage=storage,
                db=db,
                processor=processor,
            )

    results = await asyncio.gather(*[_bounded(r) for r in pending])
    success_count = sum(1 for r in results if r)

    log.success(f"Extraction complete: {success_count}/{len(pending)} articles extracted")
    log.debug("← run_extraction_pipeline done")
    return success_count
