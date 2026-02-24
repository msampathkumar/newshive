"""
Application-wide configuration settings for NewsHive.
"""
from pathlib import Path

# -----------------------------------------------------------------------------
# Core File Paths
# -----------------------------------------------------------------------------
DEFAULT_DATA_DIR: Path = Path("data")
DEFAULT_DB_PATH: Path = Path("brain/page_index.db")

# Subdirectory names under the data directory
INDEX_HTML_DIR_NAME: str = "blog_index_html"
ARTICLE_HTML_DIR_NAME: str = "article_html"
EXTRACTED_ARTICLES_DIR_NAME: str = "extracted_articles"

# -----------------------------------------------------------------------------
# Collection & Discovery Settings
# -----------------------------------------------------------------------------
# Timeout for fetching individual web pages (in seconds)
PAGE_TIMEOUT_SECONDS: int = 120

# Days to search back for a prior-day snapshot to compute deltas against
MAX_LOOKBACK_DAYS: int = 10

# List of regex patterns for URLs to ignore during article discovery
URL_IGNORE_PATTERNS: list[str] = [
    r".*\.xml$",  # Ignore all URLs ending with .xml
]

# Default concurrency settings for collection
DEFAULT_SOURCE_CONCURRENCY: int = 4
DEFAULT_ARTICLE_CONCURRENCY: int = 5

# -----------------------------------------------------------------------------
# Content Processing & AI Settings
# -----------------------------------------------------------------------------
# Default model name for Ollama
DEFAULT_OLLAMA_MODEL: str = "gemma3:1b"

# Default concurrency for running AI extractions in parallel
DEFAULT_EXTRACTION_CONCURRENCY: int = 3

# System prompt for the summarization LLM
LLM_SYSTEM_PROMPT: str = (
    "You are an expert AI news summarizer for a highly technical audience. "
    "Your readers are developers with 1 to 14 years of Software Development Experience. "
    "They are especially fans of Google Cloud and Gemini. "
    "Summarize the following text into clear, concise Markdown. "
    "Extract the key takeaway, especially highlighting anything related to "
    "Google Cloud, Vertex AI, Gemini, or general AI developer news. "
    "Do NOT include conversational filler like 'Here is the summary'."
)

# Regex to find GitHub repository URLs
GITHUB_REPO_PATTERN: str = r"https?://(?:www\.)?github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+"

# -----------------------------------------------------------------------------
# Database Settings
# -----------------------------------------------------------------------------
# Names of the tables in the SQLite database
SOURCES_TABLE_NAME: str = "blog_sources"
ARTICLES_TABLE_NAME: str = "blog_articles"
