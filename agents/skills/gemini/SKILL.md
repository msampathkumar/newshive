# Newshive Skill

## Description
This skill enables the Gemini agent to interact with the Newshive tool. It can be used to discover, scrape, process, and summarize AI news articles from various sources. It now extracts published dates, GitHub links, and allows for configurable page timeouts and URL filtering. The `make clean` command has also been enhanced for a full project reset.

## Capabilities

### Summarize AI News
- **Functionality**: Processes a given set of AI news articles to extract key information and generate concise summaries.
- **Usage**: Integrate with news feeds or article lists to get quick overviews.

### Article Management
- **Functionality**: Manages metadata for discovered articles, including storage and retrieval.
- **Usage**: Track and organize AI news articles for later review or analysis.

## Commands

### `newshive setup`
- **Description**: Runs the internal setup wizard for Newshive. This command should be run once to configure the tool.

### `newshive collect`
- **Description**: Fetches blog index pages, computes new article deltas, downloads new articles, and registers them in the database.
- **Usage**: `newshive collect`

### `newshive process`
- **Description**: Runs AI extraction on downloaded articles. This includes extracting published dates, article titles, and GitHub links, and saving Markdown summaries with a metadata header.
- **Usage**: `newshive process`

### `newshive run <text>`
- **Description**: Executes the primary functionality of News Hive with the provided text input.
- **Example**: `newshive run "Summarize the latest breakthroughs in AI ethics."`

### `newshive run --file <path>`
- **Description**: Executes the primary functionality of News Hive using content from a specified file.
- **Example**: `newshive run --file "articles/ai_trends.txt"`

## Integration with Gemini Agent
- **Installation**: Run `make gemini-install` in the project root to install this skill.
- **Uninstallation**: Run `make gemini-uninstall` to remove this skill.

## Mission Guidelines for the Agent
- Use this tool when the user needs to process, manage, or summarize AI-related news content.
- The tool can discover, scrape, process (extracting date, title, GitHub links), and store article data.
- It also supports configurable page timeouts and URL ignore patterns.
- Prioritize using the `newshive setup` command for initial configuration.
