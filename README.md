# Newshive

A **blog-index monitor pipeline** that tracks AI/ML blogs, detects new posts daily, and uses a pluggable LLM backend to extract and summarize content. It defaults to a local [Ollama](https://ollama.com) model, enabling powerful AI analysis on your machine without requiring cloud APIs.

```
blog index page → delta URLs → download articles → AI extraction → Markdown summaries
```

---

## Features

- 🔍 **Smart delta detection** — compares today's blog index against yesterday's snapshot; only processes genuinely new posts
- ⚡ **Parallel collection** — `asyncio.gather` fetches multiple sources and articles concurrently
- 🧠 **Pluggable AI Backend** — defaults to local extraction with [Ollama](https://ollama.com) (`gemma3:1b`), but is designed to be extensible for other models or cloud-based LLM APIs.
- 🎨 **Colored logging** — per-module ANSI colors, RED reserved for errors; toggle with `--no-color`
- 🗃️ **SQLite index** — lightweight, portable, no server needed
- 🧪 **39 tests** — full unit-test coverage of core logic

---

## Prerequisites

| Tool   | Version | Install                                            |
| ------ | ------- | -------------------------------------------------- |
| Python | ≥ 3.9   | [python.org](https://python.org)                   |
| uv     | latest  | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Ollama | latest  | [ollama.com](https://ollama.com)                   |

> **Note**: While Ollama is the default backend, the `ContentProcessor` can be extended to support other LLM providers like OpenAI, Anthropic, or any service accessible via an API.

```bash
# Pull the default model
ollama pull gemma3:1b
```

---

## Installation

```bash
git clone https://github.com/youruser/newshive
cd newshive
uv sync
```

---

## Quick Start

```bash
# 1. Add blog index URLs to monitor
uv run newshive source add https://huggingface.co/blog
uv run newshive source add https://lilianweng.github.io/
uv run newshive source add https://karpathy.ai/

# 2. Collect new articles (fetch index → delta → download)
uv run newshive collect

# 3. Extract & summarize downloaded articles
uv run newshive process

# 4. Or run both steps at once
uv run newshive run
```

---

## Commands

### `source` — Manage monitored blogs

```bash
uv run newshive source add <url> [--label "Name"]
uv run newshive source list
uv run newshive source remove <url>
```

> **Note:** `source add` automatically creates an empty prior-day snapshot so your first `collect` always has a baseline to diff against.

### `collect` — Fetch & download new articles

```bash
uv run newshive collect [--date YYYYMMDD] [--max-lookback 10] \
  [--source-concurrency 4] [--article-concurrency 5]
```

For each source URL:
1. Fetches the index page → saves to `data/blog_index_html/YYYYMMDD/`
2. Extracts all child links (BeautifulSoup)
3. Computes delta vs prior-day snapshot (up to 10 days lookback)
4. Filters same-domain sub-path URLs only
5. Skips already-registered articles
6. Downloads new articles → `data/article_html/YYYYMMDD/`
7. Registers in `brain/page_index.db`

### `process` — AI extraction

```bash
uv run newshive process [--date YYYYMMDD] [--model gemma3:1b] [--concurrency 3]
```

Runs the configured LLM backend (defaulting to a local Ollama model) on all downloaded articles and saves Markdown summaries to `data/extracted_articles/YYYYMMDD/`. Summaries are prepended with a metadata header including title, published date, and URL.

### `run` — End-to-end

```bash
uv run newshive run [--date YYYYMMDD] [--model gemma3:1b] [--max-lookback 10]
```

### Global Flags

```bash
--no-color    Disable ANSI colors (or set NO_COLOR=1)
--debug       Enable DEBUG-level log output
--db-path     Path to SQLite DB (default: brain/page_index.db)
--data-dir    Path to data folder (default: data/)
```

---

## Data Layout

```
data/
├── blog_index_html/
│   └── 20260224/
│       └── huggingface-co-blog.html     ← daily index snapshot
├── article_html/
│   └── 20260224/
│       └── huggingface-co-blog-...html  ← raw article HTML
└── extracted_articles/
    └── 20260224/
        └── huggingface-co-blog-...md    ← AI-generated summary

brain/
└── page_index.db   ← SQLite (blog_sources + blog_articles tables)
```

---

## Configuration

| Option                  | Default     | Description                              |
| ----------------------- | ----------- | ---------------------------------------- |
| `PAGE_TIMEOUT_SECONDS`    | `120`       | Timeout for downloading individual articles (seconds)    |
| `URL_IGNORE_PATTERNS`   | `["*.xml$"]`| Regex patterns for URLs to ignore during collection      |
| `--model`               | `gemma3:1b` | Any Ollama model name                    |
| `--max-lookback`        | `10`        | Days to search back for a prior snapshot |
| `--source-concurrency`  | `4`         | Parallel source index fetches            |
| `--article-concurrency` | `5`         | Parallel article downloads               |
| `NO_COLOR=1`            | off         | Disable ANSI colors                      |

---

## Development

```bash
# Run tests
uv run pytest -v

# Clean up build artifacts, cache, generated data, and the SQLite database
make clean

# Run with debug logging
uv run newshive --debug run

# Run with no color (CI-friendly)
NO_COLOR=1 uv run newshive run
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and [DESIGN.md](DESIGN.md) for architecture decisions.

---

## License

Apache 2.0
