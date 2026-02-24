"""
ContentProcessor — uses a local LLM via Ollama to extract and summarize article text for News Hive.
"""
import ollama

from newshive.log import ColorLogger

log = ColorLogger("content_processor")


class ContentProcessor:
    """Uses a local LLM via Ollama to summarize article text into Markdown."""

    def __init__(self, model_name: str = "gemma3:1b"):
        self.model_name = model_name
        log.debug(f"→ ContentProcessor init: model={model_name}")

    def summarize(self, text: str) -> str:
        """
        Send article text to the local LLM and return a Markdown summary.
        Designed to be run in a thread executor (it's synchronous/blocking).
        """
        log.debug(f"→ summarize: text_length={len(text)}")

        system_prompt = (
            "You are an expert AI news summarizer for a highly technical audience. "
            "Your readers are developers with 1 to 14 years of Software Development Experience. "
            "They are especially fans of Google Cloud and Gemini. "
            "Summarize the following text into clear, concise Markdown. "
            "Extract the key takeaway, especially highlighting anything related to "
            "Google Cloud, Vertex AI, Gemini, or general AI developer news. "
            "Do NOT include conversational filler like 'Here is the summary'."
        )

        response = ollama.chat(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": text},
            ]
        )

        result = response.message.content
        log.debug(f"← summarize done: output_length={len(result)}")
        return result
