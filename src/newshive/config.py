"""
Application-wide configuration settings for NewsHive.
"""

# Core Configuration
# ------------------

# Timeout for fetching individual web pages (in seconds).
# This applies to HTTP requests made to download article content.
PAGE_TIMEOUT_SECONDS: int = 120 # 2 minutes

# URL Filtering Rules
# -------------------

# List of regex patterns for URLs to ignore during article discovery.
# URLs matching any of these patterns will be skipped during collection.
URL_IGNORE_PATTERNS: list[str] = [
    r".*\.xml$",  # Ignore all URLs ending with .xml
    # Add other patterns here as needed (e.g., specific domains, paths)
]

# Example of other potential config settings:
# ------------------------------------------
# MAX_ARTICLES_PER_COLLECTION: int = 100
# DEFAULT_OLLAMA_MODEL: str = "gemma3:1b"
# MAX_CONCURRENT_SOURCE_FETCHES: int = 4
# MAX_CONCURRENT_ARTICLE_DOWNLOADS: int = 5
# MAX_CONCURRENT_EXTRACTIONS: int = 3
