"""Fetch trending repos from OSS Insight and enrich with GitHub API data."""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from urllib.error import HTTPError

logger = logging.getLogger(__name__)

OSS_INSIGHT_URL = "https://api.ossinsight.io/v1/trends/repos?period=past_month"
GITHUB_API_URL = "https://api.github.com/repos"
MIN_REPOS = 20


def fetch_trending(limit: int = 50) -> list[dict]:
    """Fetch top trending repos from OSS Insight API.

    Returns the top `limit` repos sorted by total_score descending.
    Raises ValueError if fewer than MIN_REPOS are returned.
    """
    req = urllib.request.Request(OSS_INSIGHT_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    rows = data.get("data", {}).get("rows", [])
    if len(rows) < MIN_REPOS:
        raise ValueError(f"Only {len(rows)} repos returned, expected >= {MIN_REPOS}")

    repos = []
    for row in rows[:limit]:
        repos.append({
            "repo_name": row["repo_name"],
            "url": f"https://github.com/{row['repo_name']}",
            "primary_language": row.get("primary_language") or "Unknown",
            "description": row.get("description", ""),
            "period_stars": row.get("stars", 0),
            "total_score": row.get("total_score", 0),
        })

    return repos


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

    On per-repo failure, falls back to license="Unknown" and
    total_stars=period_stars.
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
            total_stars = repo["period_stars"]

        enriched.append({
            **repo,
            "license": license_name,
            "total_stars": total_stars,
        })

    return enriched
