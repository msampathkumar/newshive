"""
ContentProcessor — uses a local LLM via Ollama to extract and summarize article text for News Hive.
"""
import ollama
import re
import trafilatura
from datetime import datetime
from bs4 import BeautifulSoup

from newshive.log import ColorLogger
from newshive.config import (
    DEFAULT_OLLAMA_MODEL,
    LLM_SYSTEM_PROMPT,
    GITHUB_REPO_PATTERN,
)

log = ColorLogger("content_processor")


class ContentProcessor:
    """Uses a local LLM via Ollama to summarize article text into Markdown."""

    def __init__(self, model_name: str = DEFAULT_OLLAMA_MODEL):
        self.model_name = model_name
        log.debug(f"→ ContentProcessor init: model={model_name}")

    def extract_title(self, raw_html: str) -> str | None:
        """
        Extracts the article title from raw HTML using BeautifulSoup.
        Looks for <title> tag first, then <h1> or other common title tags.
        """
        log.debug(f"→ extract_title: raw_html_len={len(raw_html)}")
        soup = BeautifulSoup(raw_html, "html.parser")
        
        # Try to get from <title> tag
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            log.debug(f"← extract_title: from <title> - {title_tag.string.strip()}")
            return title_tag.string.strip()

        # Try to get from <h1> tag
        h1_tag = soup.find("h1")
        if h1_tag and h1_tag.string:
            log.debug(f"← extract_title: from <h1> - {h1_tag.string.strip()}")
            return h1_tag.string.strip()

        log.debug(f"← extract_title: No title found.")
        return None

    def extract_text_and_date(self, raw_html: str, url: str) -> tuple[str | None, str | None]:
        """
        Extracts main article text and published date from raw HTML using Trafilatura.
        Returns a tuple: (text, published_date_iso_format).
        """
        log.debug(f"→ extract_text_and_date: url={url}")
        downloaded = trafilatura.bare_extraction(
            raw_html,
            url=url,
            include_comments=False,
            include_images=False,
            include_formatting=False,
            include_links=True, # We need links for GitHub extraction later
        )

        text = downloaded.text if downloaded and downloaded.text else None
        date = downloaded.date if downloaded and downloaded.date else None
        
        if date:
            # Ensure date is in ISO format
            try:
                date_obj = datetime.fromisoformat(date)
                date = date_obj.isoformat()
            except ValueError:
                date = None # Fallback if trafilatura date is not ISO convertible

        log.debug(f"← extract_text_and_date: text_len={len(text) if text else 0}, date={date}")
        return text, date

    def extract_github_links(self, text: str) -> list[str]:
        """
        Extracts GitHub repository links from the given text.
        Looks for patterns like "github.com/user/repo".
        """
        log.debug(f"→ extract_github_links: text_length={len(text)}")
        found_links = re.findall(GITHUB_REPO_PATTERN, text)
        # Remove duplicates by converting to set and back to list
        unique_links = list(set(found_links))
        
        log.debug(f"← extract_github_links: found {len(unique_links)} links")
        return unique_links

    def summarize(self, text: str) -> str:
        """
        Send article text to the local LLM and return a Markdown summary.
        Designed to be run in a thread executor (it's synchronous/blocking).
        """
        log.debug(f"→ summarize: text_length={len(text)}")

        response = ollama.chat(
            model=self.model_name,
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user",   "content": text},
            ]
        )

        result = response.message.content
        log.debug(f"← summarize done: output_length={len(result)}")
        return result

    def process_article(self, raw_html: str, url: str, scraped_at: str) -> dict:
        """
        Orchestrates extraction of text, published date, GitHub links,
        and summary from raw article HTML.
        Returns a dictionary of all extracted and processed data.
        """
        log.debug(f"→ process_article: url={url}")

        # Step 0: Extract Title
        title = self.extract_title(raw_html) or "Untitled Article"

        # Step 1: Extract main text and published date
        extracted_text, published_date = self.extract_text_and_date(raw_html, url)

        # Step 2: Extract GitHub links (from the full raw HTML if text extraction is partial)
        # Using raw_html for GitHub link extraction to catch all links
        github_links = self.extract_github_links(raw_html)

        summary = None
        if extracted_text:
            # Step 3: Summarize the extracted text
            summary = self.summarize(extracted_text)
            if summary:
                # Prepend metadata to the summary
                date_to_display = published_date or scraped_at
                metadata_header = (
                    f"# Title: {title}\n"
                    f"* Date: {date_to_display}\n"
                    f"* URL link: <{url}>\n"
                )
                summary = metadata_header + summary
        else:
            log.warning(f"No text extracted for {url}, skipping summarization.")


        log.debug(f"← process_article done: summary_len={len(summary) if summary else 0}, date={published_date}, github_links={len(github_links)}")
        return {
            "extracted_text": extracted_text,
            "published_date": published_date,
            "github_links": github_links,
            "summary": summary,
        }
