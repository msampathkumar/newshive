import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ai_news_summarizer.cli import cli

if __name__ == "__main__":
    cli()
