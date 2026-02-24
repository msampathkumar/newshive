# Design Document — AI News Summarizer

> Architecture reference for developers. Explains *why* the system is built the way it is, not just *what* it does.

---

## Problem Statement

Most AI news aggregators rely on RSS feeds or third-party APIs. This project takes a different approach: it **monitors the blog index pages directly**, computes a delta of new article URLs against a prior-day snapshot, and uses a local LLM to extract and summarize content — with no external services required beyond Ollama.

---

## Architecture Overview

```mermaid
graph TD
    CLI["CLI (cli.py)"]
    CLI --> Pipeline["Pipeline (pipeline.py)"]
    Pipeline -->|asyncio.gather| Crawler["BlogCrawler (crawler.py)"]
    Pipeline -->|asyncio.gather| Summarizer["Summarizer (summarizer.py)"]
    Crawler --> Storage["StorageManager (storage.py)"]
    Crawler --> DB["DataManager (database.py)"]
    Summarizer --> Storage
    Summarizer --> DB
    All["All modules"] --> Log["ColorLogger (log.py)"]
```

### Module Responsibilities

| Module          | Single Responsibility                          |
| --------------- | ---------------------------------------------- |
| `log.py`        | ANSI-colored structured logging; nothing else  |
| `storage.py`    | All file I/O; no business logic                |
| `database.py`   | SQLite read/write; no business logic           |
| `crawler.py`    | HTTP + HTML parsing + delta + domain filter    |
| `pipeline.py`   | Orchestration only; delegates to other modules |
| `summarizer.py` | LLM call only; no file I/O                     |
| `cli.py`        | User interface only; no business logic         |

---

## Key Design Decisions

### 1. Blog Index as Source of Truth

Rather than crawling links recursively (the old approach), the system treats each **blog index page** (e.g. `https://huggingface.co/blog`) as the authoritative list of posts. This is more predictable, faster, and avoids crawling unrelated pages.

**Trade-off:** The index page must list all recent posts in its HTML (not behind JavaScript rendering). Sites that paginate or use JS-only rendering may not work.

### 2. Delta via Filesystem Snapshots

New articles are discovered by:
1. Saving today's index HTML → `blog_index_html/YYYYMMDD/<url>.html`
2. Loading yesterday's saved HTML (walking back up to 10 days if needed)
3. Extracting links from both and computing the set difference

This approach requires **no database diff, no external state**, and works even if the pipeline misses days. The lookback window ensures resilience against pipeline failures.

```mermaid
sequenceDiagram
    participant C as BlogCrawler
    participant S as StorageManager
    C->>S: fetch_index_page(url, today)
    S-->>C: raw HTML
    C->>S: find_most_recent_index_date(url, lookback=10)
    S-->>C: "20260222" (e.g.)
    C->>S: get_index_html(url, "20260222")
    S-->>C: prior HTML
    C->>C: extract_child_urls() × 2
    C->>C: compute_delta(current, prior)
    C->>C: filter_same_domain(base_url, delta)
```

### 3. Same-Domain + Sub-Path Filtering

From the delta, only URLs matching **both** the domain AND the base path prefix are kept:

```
base_url = "https://example.com/blog"

https://example.com/blog/post-1      ✅  same domain, sub-path of /blog
https://example.com/blog/tag/python  ✅
https://example.com/about            ❌  different path (/about)
https://other.com/blog/post          ❌  different domain
https://example.com/blog             ❌  the index itself
```

This prevents downloading category pages, tag archives, or unrelated site sections.

### 4. Parallelism via `asyncio.gather` + Semaphore

All I/O-bound work (HTTP fetches) is parallelized without external dependencies:

```python
# Bounded concurrency via semaphore
sem = asyncio.Semaphore(concurrency)

async def _bounded(url):
    async with sem:
        return await download_article(url)

results = await asyncio.gather(*[_bounded(u) for u in urls])
```

Two semaphores are used independently:
- `source_concurrency` (default 4) — parallel index page fetches
- `article_concurrency` (default 5) — parallel article downloads

Ollama calls (synchronous/blocking) are run via `loop.run_in_executor()` to avoid blocking the event loop.

### 5. Database Schema (no FK)

```sql
CREATE TABLE blog_sources (
    url       TEXT PRIMARY KEY,
    label     TEXT,
    added_at  TEXT
);

CREATE TABLE blog_articles (
    url          TEXT PRIMARY KEY,
    source_url   TEXT,         -- which index page this came from
    status       TEXT,         -- downloaded | extracted | error_fetch | error_llm
    scraped_at   TEXT,
    extracted_at TEXT
);
```

The old schema had `articles → urls` with a FK constraint, which required pre-registering every URL before processing it. Articles are now discovered dynamically, so no FK is needed. `source_url` is a soft reference for traceability.

**Statuses:**

| Status        | Meaning                            |
| ------------- | ---------------------------------- |
| `downloaded`  | HTML saved, pending AI extraction  |
| `extracted`   | AI summary generated and saved     |
| `error_fetch` | HTTP/network error during download |
| `error_llm`   | AI extraction failed               |
| `skipped`     | Manually skipped                   |

### 6. Prior-Day Seed on `source add`

When `source add <url>` is called for the first time, the system writes an **empty HTML file** to `blog_index_html/<yesterday>/`. This ensures the first real `collect` run always has a prior-day baseline, preventing all historical articles from being treated as "new" on day one.

```
data/blog_index_html/
├── 20260223/
│   └── huggingface-co-blog.html   ← empty seed (created by source add)
└── 20260224/
    └── huggingface-co-blog.html   ← real index snapshot (created by collect)
```

### 7. Colored Logging

Each module has a dedicated ANSI color for its log prefix. This makes multi-module output easy to trace in `--debug` mode without a log aggregator. RED is strictly reserved for warnings and errors.

| Module       | Color   | Why                                 |
| ------------ | ------- | ----------------------------------- |
| `crawler`    | Cyan    | Dominant output during collection   |
| `storage`    | Blue    | Secondary, file I/O confirmations   |
| `database`   | Magenta | Distinct from storage; often paired |
| `pipeline`   | Green   | Progress/success visibility         |
| `summarizer` | Yellow  | Warm; long-running AI work          |
| Errors       | Red     | Immediate visual attention          |

Color output is disabled by setting `NO_COLOR=1` or passing `--no-color` to any command.

---

## Data Flow: End-to-End

```mermaid
sequenceDiagram
    participant U as User / Scheduler
    participant CLI
    participant P as Pipeline
    participant C as BlogCrawler
    participant S as StorageManager
    participant DB as DataManager
    participant LLM as Summarizer (Ollama)

    U->>CLI: ai-news-summarizer run
    CLI->>P: run_collection_pipeline(sources, date)
    loop For each source (parallel)
        P->>C: collect_source(url, date)
        C->>S: fetch_index_page → save blog_index_html/
        C->>S: find prior-day HTML (lookback 10 days)
        C->>C: delta + domain filter + registered check
        C->>S: download_articles_batch → save article_html/
        C->>DB: register_article(url, status=downloaded)
    end
    P->>CLI: list of saved article URLs

    CLI->>P: run_extraction_pipeline(pending, date)
    loop For each article (parallel)
        P->>S: get_article_html(url, date)
        P->>LLM: summarize(text)  ← run_in_executor
        P->>S: save_extracted_article → extracted_articles/
        P->>DB: update_article_status(url, extracted)
    end
    P->>CLI: count extracted
```

---

## Extension Points

### Add a new content domain
No code changes needed — just `source add <url>`. The domain filtering is automatic.

### Use a different LLM
Pass `--model <ollama-model-name>` at runtime. The `Summarizer` class is model-agnostic.

### Change the extraction prompt
Edit `Summarizer.summarize()` in `summarizer.py`. The system prompt is in one place.

### Add a new output format
Add a new method to `StorageManager` (e.g. `save_json_article`) and call it from `pipeline.py`. No other changes required.

### Schedule daily runs
```bash
# crontab -e
0 7 * * * cd /path/to/ai-news-summarizer && uv run ai-news-summarizer run --no-color >> logs/daily.log 2>&1
```

---

## Testing Philosophy

- **Unit tests only** for core logic (no network in tests)
- `StorageManager` is tested against a real `tmp_path` filesystem
- `DatabaseManager` is tested against a real in-memory SQLite file in `tmp_path`
- `BlogCrawler` uses `MagicMock` for `StorageManager` and `respx` for HTTP
- No test should depend on external services (Ollama, internet)

```
tests/
├── test_crawler.py    ← link extraction, delta, domain filter, fallback
├── test_storage.py    ← all folder types, seed, lookback
├── test_database.py   ← CRUD for both tables, statuses
├── test_scraper.py    ← legacy (kept for compatibility)
├── test_cli.py        ← Click command smoke tests
└── test_summarizer.py ← mocked Ollama
```

---

## Known Limitations

| Limitation                       | Workaround                                                                    |
| -------------------------------- | ----------------------------------------------------------------------------- |
| JavaScript-rendered index pages  | Use a pre-fetched static HTML alternative URL                                 |
| Blogs without a list-style index | Not currently supported                                                       |
| Rate limiting by target sites    | Reduce `--article-concurrency`                                                |
| Very large article HTML          | Trafilatura's extraction may truncate; consider `--model` with larger context |
