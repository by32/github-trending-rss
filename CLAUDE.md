# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A static RSS feed site hosted on GitHub Pages at `https://byoungs.github.io/github-trending-rss/feed.xml`. A GitHub Actions cron workflow runs on the 1st of each month, fetches trending repo data, generates editorial summaries via Claude Sonnet, and commits an updated `feed.xml`.

## Architecture

```
OSS Insight API → src/fetch.py (top 50 repos + GitHub API enrichment)
    → src/editorial.py (Claude Sonnet categorization + summaries)
    → src/feed_writer.py (build RSS item XML, prepend to feed.xml)
    → src/main.py (orchestrator, entry point)
```

## Key Commands

```bash
uv sync                        # Install dependencies
uv run pytest                   # Run tests
uv run ruff check src/ tests/   # Lint
uv run python -m src.main       # Run pipeline locally (needs ANTHROPIC_API_KEY)
```

## Repository Structure

- `feed.xml` — RSS 2.0 feed with `content:encoded` CDATA blocks. New items are **prepended** (most recent first).
- `index.html` — Static landing page. Rarely changes.
- `src/fetch.py` — OSS Insight + GitHub REST API data collection
- `src/editorial.py` — Claude Sonnet prompt construction + response parsing
- `src/feed_writer.py` — XML item generation + feed prepend logic
- `src/main.py` — Pipeline orchestrator
- `.github/workflows/monthly-digest.yml` — Cron workflow (1st of month, 12:00 UTC)

## Feed Format Conventions

- RSS 2.0 with `xmlns:atom` and `xmlns:content` namespaces.
- GUID format: `github-trending-YYYY-MM` (the month being summarized, not publication date).
- Update `<lastBuildDate>` whenever the feed changes.
- 5 categories: AI / Machine Learning, Developer Tools / Skills Ecosystem, Web Infrastructure and Browser Automation, Education and Research, Data OSINT and Utilities.
- HTML tables in `<content:encoded>` CDATA with inline CSS (border-collapse, font-family:sans-serif, etc.).
- `<description>` is plain-text; `<content:encoded>` has full HTML.
- String-based XML manipulation (not ElementTree) to preserve CDATA and namespace prefixes.

## Deployment

Commits to `main` are served by GitHub Pages. No build step.

## Environment Variables

- `ANTHROPIC_API_KEY` — required, Anthropic API key for Claude Sonnet
- `GITHUB_TOKEN` — optional (automatic in Actions), used for GitHub REST API enrichment
