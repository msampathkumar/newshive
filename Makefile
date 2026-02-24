.PHONY: install uninstall test build clean setup lint help gemini-install gemini-uninstall agent-onboard

help:
	@echo "Available commands:"
	@echo "  make install         - Install the tool globally using 'uv tool install'"
	@echo "  make uninstall       - Uninstall the tool globally"
	@echo "  make test            - Run all tests using pytest"
	@echo "  make lint            - Run linter to format the code"
	@echo "  make build           - Build source and wheel distributions"
	@echo "  make clean           - Remove build artifacts and cache"
	@echo "  make setup           - Run the internal setup wizard"
	@echo "  make gemini-install  - Install the skill for the Gemini Agent"
	@echo "  make gemini-uninstall - Remove the skill for the Gemini Agent"
	@echo "  make agent-onboard   - Display the onboarding guide for an AI agent"

install:
	uv tool install . --force

uninstall:
	uv tool uninstall news-hive

test:
	uv run pytest

lint:
	uv run ruff check . --fix
	uv run ruff format .

build:
	uv build

clean:
	rm -rf dist/ .pytest_cache/ .venv/
	find . -type d -name "__pycache__" -exec rm -rf {} +

setup:
	uv run news-hive setup

gemini-install:
	@mkdir -p ~/.gemini/skills/news-hive
	@cp -r agents/skills/gemini/* ~/.gemini/skills/news-hive/
	@echo "✨ NewsHive skill installed to ~/.gemini/skills/news-hive/"

gemini-uninstall:
	@rm -rf ~/.gemini/skills/news-hive
	@echo "🗑️ NewsHive skill removed from ~/.gemini/skills/news-hive/"

agent-onboard:
	@echo "🤖 [bold cyan]Agent Onboarding: news-hive[/bold cyan]"
	@echo "--------------------------------------------------"
	@echo "Welcome, Agent. This is a template for onboarding."
	@echo ""
	@echo "1. Capabilities:"
	@echo "   - Manages and summarizes AI news articles from various sources."
	@echo "   - Organizes and tracks metadata for discovered articles."
	@echo ""
	@echo "2. Your Interface:"
	@echo "   - Primary Command: 'news-hive run <text>'"
	@echo "   - File Input: 'news-hive run --file <path>'"
	@echo ""
	@echo "3. Integration:"
	@echo "   - Your skill definition is located in 'agents/skills/gemini/SKILL.md'."
	@echo "   - Run 'make gemini-install' to add this capability to your core system."
	@echo ""
	@echo "4. Mission Guidelines:"
	@echo "   - Use this tool when the user needs to process, manage, or summarize AI-related news content.
	- The tool can discover, scrape, process, and store article data.
	- Prioritize using the 'news-hive setup' command for initial configuration."
	@echo "--------------------------------------------------"
