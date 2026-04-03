# GitHub Trending Digest — RSS Feed

Monthly RSS feed of the top 50 trending GitHub repositories, auto-generated and hosted on GitHub Pages.

## Subscribe

Add this URL to your RSS reader:

```
https://byoungs.github.io/github-trending-rss/feed.xml
```

## How it works

A GitHub Actions workflow runs on the 1st of each month:

1. Fetches trending repos from the [OSS Insight](https://ossinsight.io) API
2. Enriches each repo with license and total star count via the GitHub REST API
3. Sends the structured data to Claude Sonnet for categorization and summary writing
4. Prepends a new `<item>` to `feed.xml` and pushes to `main`

GitHub Pages serves the updated feed automatically.

## What's included

Each monthly item covers ~50 repos grouped by category (AI/ML, DevTools, Infrastructure, etc.) with repo links, language, license, star count, and a short summary.

## Development

```bash
uv sync                        # Install dependencies
uv run pytest                   # Run tests
uv run ruff check src/ tests/   # Lint
uv run python -m src.main       # Run pipeline locally (needs ANTHROPIC_API_KEY)
```

## Secrets

The workflow requires one secret configured in GitHub repo settings:

- `ANTHROPIC_API_KEY` — Anthropic API key for Claude Sonnet
