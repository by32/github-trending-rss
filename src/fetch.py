"""Fetch trending repos from github.com/trending and enrich with GitHub API data."""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from html import unescape
from urllib.error import HTTPError

logger = logging.getLogger(__name__)

# OSS Insight's trending ranking (the original source) has returned no rows
# since its GitHub event capture collapsed in March 2026, so read GitHub's own
# Trending page. It lists 25 repos in GitHub's ranking order.
TRENDING_URL = "https://github.com/trending?since=monthly"
USER_AGENT = "Mozilla/5.0 (compatible; github-trending-rss; +https://github.com/by32/github-trending-rss)"
GITHUB_API_URL = "https://api.github.com/repos"
MIN_REPOS = 20

_ARTICLE_RE = re.compile(r"<article\b[^>]*>(.*?)</article>", re.S)
_REPO_RE = re.compile(r'<h2\b[^>]*>.*?href="/([\w.-]+/[\w.-]+)"', re.S)
_DESCRIPTION_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.S)
_LANGUAGE_RE = re.compile(r'itemprop="programmingLanguage"[^>]*>([^<]+)<')
_PERIOD_STARS_RE = re.compile(r"([\d,]+)\s+stars?\s+this\s+month")


def _text(html: str) -> str:
    """Strip tags and entities and collapse whitespace."""
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def _count(text: str) -> int:
    digits = text.replace(",", "")
    return int(digits) if digits.isdigit() else 0


def parse_trending_page(html: str) -> list[dict]:
    """Parse repos, in ranking order, from a github.com/trending page."""
    repos = []
    for article in _ARTICLE_RE.findall(html):
        repo_match = _REPO_RE.search(article)
        if not repo_match:
            continue
        repo_name = repo_match.group(1)

        description = _DESCRIPTION_RE.search(article)
        language = _LANGUAGE_RE.search(article)
        total_stars = re.search(
            rf'href="/{re.escape(repo_name)}/stargazers"[^>]*>(.*?)</a>', article, re.S
        )
        period_stars = _PERIOD_STARS_RE.search(_text(article))

        repos.append({
            "repo_name": repo_name,
            "url": f"https://github.com/{repo_name}",
            "primary_language": language.group(1).strip() if language else "Unknown",
            "description": _text(description.group(1)) if description else "",
            "period_stars": _count(period_stars.group(1)) if period_stars else 0,
            "total_stars": _count(_text(total_stars.group(1))) if total_stars else 0,
        })
    return repos


def fetch_trending(limit: int = 50) -> list[dict]:
    """Fetch this month's trending repos from github.com/trending.

    Returns up to `limit` repos in GitHub's ranking order.
    Raises ValueError if fewer than MIN_REPOS are parsed, which also catches
    a change to the page's markup.
    """
    req = urllib.request.Request(TRENDING_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    repos = parse_trending_page(html)
    if len(repos) < MIN_REPOS:
        raise ValueError(f"Only {len(repos)} repos parsed, expected >= {MIN_REPOS}")

    return repos[:limit]


def _github_get(repo_name: str, token: str | None) -> dict:
    """GET a single repo from the GitHub REST API with retry."""
    url = f"{GITHUB_API_URL}/{repo_name}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except HTTPError as e:
            last_exc = e
            if e.code in (403, 429) and attempt < 2:
                time.sleep(2)
                continue
            raise
        except Exception as e:
            last_exc = e
            if attempt < 2:
                time.sleep(2)
                continue
            raise

    raise last_exc  # type: ignore[misc]


def enrich_with_github(repos: list[dict], token: str | None = None) -> list[dict]:
    """Add license and total star count from GitHub REST API.

    On per-repo failure, falls back to license="Unknown" and the star count
    from the Trending page (or period_stars when that is missing).
    """
    enriched = []
    for repo in repos:
        try:
            gh = _github_get(repo["repo_name"], token)
            license_info = gh.get("license") or {}
            license_name = license_info.get("spdx_id") or license_info.get("name") or "Unknown"
            if license_name == "NOASSERTION":
                license_name = "Unknown"
            total_stars = gh.get("stargazers_count", repo["period_stars"])
        except Exception:
            logger.warning("GitHub API failed for %s, using fallback", repo["repo_name"])
            license_name = "Unknown"
            total_stars = repo.get("total_stars") or repo["period_stars"]

        enriched.append({
            **repo,
            "license": license_name,
            "total_stars": total_stars,
        })

    return enriched
