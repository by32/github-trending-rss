"""Monthly GitHub Trending Digest pipeline orchestrator."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from email.utils import format_datetime

from src.editorial import build_prompt, call_claude, parse_editorial_response
from src.feed_writer import build_item_xml, prepend_item_to_feed
from src.fetch import enrich_with_github, fetch_trending

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

FEED_PATH = "feed.xml"


def _previous_month(now: datetime) -> tuple[str, str]:
    """Return (month_label, guid_month) for the previous month.

    Example: if now is 2026-05-01, returns ("April 2026", "2026-04").
    """
    if now.month == 1:
        year, month = now.year - 1, 12
    else:
        year, month = now.year, now.month - 1

    dt = datetime(year, month, 1)
    return dt.strftime("%B %Y"), f"{year:04d}-{month:02d}"


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    github_token = os.environ.get("GITHUB_TOKEN")

    now = datetime.now(timezone.utc)
    month_label, guid_month = _previous_month(now)
    pub_date = format_datetime(now)
    build_date = pub_date

    logger.info("Generating digest for %s", month_label)

    # 1. Fetch trending repos
    logger.info("Fetching trending repos from OSS Insight...")
    repos = fetch_trending(limit=50)
    logger.info("Fetched %d repos", len(repos))

    # 2. Enrich with GitHub API
    logger.info("Enriching with GitHub API data...")
    repos = enrich_with_github(repos, token=github_token)

    # 3. Get editorial content from Claude
    logger.info("Calling Claude Sonnet for categorization and summaries...")
    prompt = build_prompt(repos, month_label)
    response = call_claude(prompt, api_key=api_key)
    categories, description = parse_editorial_response(response)

    total = sum(len(r) for r in categories.values())
    logger.info("Claude categorized %d repos into %d categories", total, len(categories))

    # 4. Build and prepend item
    logger.info("Building RSS item and updating feed.xml...")
    item_xml = build_item_xml(
        categories=categories,
        description=description,
        month_label=month_label,
        guid_month=guid_month,
        pub_date=pub_date,
    )
    prepend_item_to_feed(FEED_PATH, item_xml, build_date)

    logger.info("Done — %s digest written to %s", month_label, FEED_PATH)


if __name__ == "__main__":
    main()
