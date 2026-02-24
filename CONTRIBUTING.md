# Contributing to AI News Summarizer

Thanks for your interest in contributing! This is a clean, modular Python project and new contributions are very welcome.

---

## Getting Started

### 1. Clone & set up

```bash
git clone https://github.com/youruser/ai-news-summarizer
cd ai-news-summarizer
uv sync          # installs all deps including dev extras
```

### 2. Run the tests

```bash
uv run pytest -v
```

All 39 tests should pass before you start making changes.

### 3. Run the full pipeline locally

```bash
# Pull the default model
ollama pull gemma3:1b

# Add a test source
uv run ai-news-summarizer source add https://huggingface.co/blog --label "HuggingFace Blog"

# Collect new articles
uv run ai-news-summarizer collect --debug

# Summarize
uv run ai-news-summarizer process --debug
```

---

## Project Structure

```
src/ai_news_summarizer/
├── log.py          ← Colored logging (start here to understand output)
├── storage.py      ← All file I/O (blog_index_html/, article_html/, extracted_articles/)
├── database.py     ← SQLite layer (blog_sources, blog_articles)
├── crawler.py      ← BlogCrawler: fetch, extract, delta, filter, download
├── pipeline.py     ← asyncio.gather orchestration
├── summarizer.py   ← Ollama LLM wrapper
└── cli.py          ← Click commands (source/collect/process/run)

tests/
├── test_crawler.py   ← 12 tests
├── test_storage.py   ← 16 tests
└── test_database.py  ← 11 tests
```

---

## Development Guidelines

### Code Style

- **Python 3.12+** — use modern syntax (`X | Y`, `match`, etc.)
- **Type hints** everywhere on public methods
- **SOLID + DRY** — one responsibility per class; no copy-paste logic
- **No global mutable state** — pass dependencies explicitly

### Logging

Use `ColorLogger` from `log.py`, not `print()` or the stdlib `logging` module directly.

```python
from ai_news_summarizer.log import ColorLogger
log = ColorLogger("my_module")   # pick a module color from MODULE_COLORS or add one

log.debug("→ my_function start: param=...")   # called at start of every function
log.info("Doing something notable")
log.success("Step complete")
log.warning("Something unexpected but recoverable")
log.error("Critical failure")
log.debug("← my_function done")              # called at end of every function
```

**Colors are pre-assigned per module** in `log.MODULE_COLORS`. When adding a new module, pick an unused color and add it to that dict. **RED is reserved for warnings and errors only.**

### Testing

- Every new module needs a corresponding `tests/test_<module>.py`
- Use `pytest` with `tmp_path` fixture for file I/O tests
- Use `unittest.mock.MagicMock` for injected dependencies (e.g. `StorageManager`)
- Use `respx` for mocking HTTP calls (already in dev deps)
- Async tests: use `@pytest.mark.asyncio`

```bash
# Run only your new tests
uv run pytest tests/test_my_module.py -v

# Run with debug logs visible
uv run pytest -v -s
```

### Adding a New Blog Source (config-level)

Just use the CLI:
```bash
uv run ai-news-summarizer source add https://newblog.com/posts
```

### Adding a New Ollama Model

Pass `--model` at runtime:
```bash
uv run ai-news-summarizer process --model llama3.2:3b
```

---

## Pull Request Checklist

- [ ] New/modified code has type hints
- [ ] New module has a `ColorLogger` at the top
- [ ] `debug` log at start and end of each public method
- [ ] Tests added/updated for changed logic
- [ ] `uv run pytest -v` passes (all green)
- [ ] No secrets or personal data in code or test fixtures
- [ ] `uv run ai-news-summarizer --help` still works correctly

---

## Dependency Management

This project uses [`uv`](https://github.com/astral-sh/uv) for dependency management.

```bash
# Add a runtime dependency
uv add some-package

# Add a dev-only dependency
uv add --dev some-package

# Sync after pulling changes
uv sync
```

Do **not** manually edit `uv.lock`. It is auto-generated.

---

## Reporting Issues

Please open a GitHub Issue with:
- OS and Python version (`python --version`)
- Full command that failed
- Full terminal output (with `--debug` flag)
- Contents of `brain/page_index.db` if relevant (use `sqlite3 brain/page_index.db .tables`)
