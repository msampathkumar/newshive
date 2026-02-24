"""
Pipeline — asyncio orchestration for the AI News Summarizer.

Two main pipelines:

1. run_collection_pipeline()
   For each source URL (in parallel):
     - Fetch index page
     - Extract + delta + filter
     - Download new articles
     - Register in database

2. run_extraction_pipeline()
   For each downloaded article (in parallel):
     - Run AI extraction (Summarizer)
     - Save to extracted_articles/YYYYMMDD/
"""
import asyncio
from datetime import datetime, timezone

from ai_news_summarizer.log import ColorLogger
from ai_news_summarizer.storage import StorageManager
from ai_news_summarizer.database import DataManager, STATUS_DOWNLOADED, STATUS_EXTRACTED, STATUS_ERROR_FETCH, STATUS_ERROR_LLM
from ai_news_summarizer.crawler import BlogCrawler
from ai_news_summarizer.summarizer import Summarizer

log = ColorLogger("pipeline")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


# ─────────────────────────────────────────────────────────────────────────────
# Collection Pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def _collect_one_source(
    source_url: str,
    date: str,
    crawler: BlogCrawler,
    db: DataManager,
    storage: StorageManager,
    max_lookback: int,
    article_concurrency: int,
) -> list[str]:
    """Handle collection for a single source URL."""
    log.debug(f"→ _collect_one_source: {source_url}")

    # Step 1-5: Discover new article URLs
    new_article_urls = await crawler.collect_source(
        source_url=source_url,
        date=date,
        registered_check=db.is_article_registered,
        max_lookback=max_lookback,
    )

    if not new_article_urls:
        log.info(f"No new articles found for: {source_url}")
        return []

    # Step 6: Download articles in parallel (bounded)
    log.info(f"Downloading {len(new_article_urls)} new articles from {source_url} ...")
    download_results = await crawler.download_articles_batch(
        new_article_urls, date, concurrency=article_concurrency
    )

    # Step 7: Register in database
    saved: list[str] = []
    for url, html in download_results.items():
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
    db: DataManager,
    storage: StorageManager,
    date: str | None = None,
    max_lookback: int = 10,
    source_concurrency: int = 4,
    article_concurrency: int = 5,
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
    date = date or _today()
    sources = db.get_blog_sources()

    if not sources:
        log.warning("No blog sources registered. Use: ai-news-summarizer source add <url>")
        return []

    log.info(f"Collection pipeline: {len(sources)} sources, date={date}")
    crawler = BlogCrawler(storage)

    # Run all sources in parallel (bounded by semaphore)
    sem = asyncio.Semaphore(source_concurrency)

    async def _bounded(source: dict) -> list[str]:
        async with sem:
            return await _collect_one_source(
                source_url=source["url"],
                date=date,
                crawler=crawler,
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
    url: str,
    date: str,
    storage: StorageManager,
    db: DataManager,
    summarizer: Summarizer,
) -> bool:
    """Run AI extraction for a single article."""
    log.debug(f"→ _extract_one_article: {url}")

    # Load saved article HTML
    if not storage.has_article_html(url, date):
        log.warning(f"Article HTML not found on disk (date={date}): {url}")
        return False

    import trafilatura
    html = storage.get_article_html(url, date)

    # Extract clean text first
    text = trafilatura.extract(html, include_links=False)
    if not text:
        log.warning(f"No text extractable from article: {url}")
        db.update_article_status(url, STATUS_ERROR_LLM)
        return False

    # Run AI summarization (run sync in executor to not block event loop)
    loop = asyncio.get_event_loop()
    try:
        summary = await loop.run_in_executor(None, summarizer.summarize, text)
    except Exception as e:
        log.error(f"AI extraction failed for {url}: {e}")
        db.update_article_status(url, STATUS_ERROR_LLM)
        return False

    # Save markdown
    storage.save_extracted_article(url, summary, date)
    db.update_article_status(url, STATUS_EXTRACTED)
    log.debug(f"← _extract_one_article done: {url}")
    return True


async def run_extraction_pipeline(
    db: DataManager,
    storage: StorageManager,
    date: str | None = None,
    model: str = "gemma3:1b",
    concurrency: int = 3,
) -> int:
    """
    Run AI extraction for all articles with status 'downloaded'.

    Returns count of successfully extracted articles.
    """
    log.debug("→ run_extraction_pipeline start")
    date = date or _today()
    pending = db.get_pending_extraction(date)

    if not pending:
        log.info("No articles pending extraction.")
        return 0

    log.info(f"Extraction pipeline: {len(pending)} articles, model={model}, date={date}")
    summarizer = Summarizer(model_name=model)

    sem = asyncio.Semaphore(concurrency)

    async def _bounded(row: dict) -> bool:
        async with sem:
            return await _extract_one_article(
                url=row["url"],
                date=date,
                storage=storage,
                db=db,
                summarizer=summarizer,
            )

    results = await asyncio.gather(*[_bounded(r) for r in pending])
    success_count = sum(1 for r in results if r)

    log.success(f"Extraction complete: {success_count}/{len(pending)} articles extracted")
    log.debug("← run_extraction_pipeline done")
    return success_count
