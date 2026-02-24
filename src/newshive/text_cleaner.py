"""
Text Cleaner for News Hive.

Provides functions to clean up extracted article text by removing boilerplate,
unwanted lines, and normalizing whitespace before sending it to an LLM.
"""
import re
from newshive.config import TEXT_CLEANING_REGEX_PATTERNS
from newshive.log import ColorLogger

log = ColorLogger("text_cleaner")

def clean_text(text: str) -> str:
    """
    Cleans the extracted text by removing boilerplate lines and normalizing whitespace.

    Args:
        text: The raw text extracted by trafilatura.

    Returns:
        A cleaner version of the text.
    """
    if not text:
        return ""

    log.debug("→ Starting text cleaning...")
    original_line_count = len(text.splitlines())

    # 1. Line-by-line removal of boilerplate
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        is_junk = False
        for pattern in TEXT_CLEANING_REGEX_PATTERNS:
            # Using re.IGNORECASE for robust matching
            if re.search(pattern, line, re.IGNORECASE):
                is_junk = True
                log.debug(f"  - Removing line matching '{pattern}': {line[:80]}...")
                break
        if not is_junk:
            cleaned_lines.append(line)

    # 2. Re-join and normalize whitespace
    # This joins the kept lines and then replaces sequences of 3 or more newlines
    # with just two newlines, effectively ensuring at most one blank line.
    text_no_junk = "
".join(cleaned_lines)
    text_normalized = re.sub(r'
{3,}', '

', text_no_junk).strip()

    final_line_count = len(text_normalized.splitlines())
    log.debug(f"← Text cleaning finished. Removed {original_line_count - final_line_count} lines.")

    return text_normalized
