"""Tests for src/fetch module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.fetch import enrich_with_github, fetch_trending, parse_trending_page

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_urlopen(data: dict):
    """Create a mock for urllib.request.urlopen that returns JSON data."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


SAMPLE_HTML = (FIXTURES / "sample_trending.html").read_text()


def _mock_html_urlopen(html: str):
    mock_resp = MagicMock()
    mock_resp.read.return_value = html.encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _page_with(count: int) -> str:
    """A trending page with `count` copies of the first fixture article, renamed."""
    article = SAMPLE_HTML.split("<article", 2)[1].split("</article>")[0]
    rows = [
        "<article" + article.replace("alice/cool-project", f"owner{i}/repo{i}") + "</article>"
        for i in range(count)
    ]
    return "<html><body>" + "\n".join(rows) + "</body></html>"


class TestParseTrendingPage:
    def test_parses_fields_in_page_order(self):
        repos = parse_trending_page(SAMPLE_HTML)

        assert [r["repo_name"] for r in repos] == ["alice/cool-project", "bob-dev/dot.files", "carol/rust_thing"]
        alice = repos[0]
        assert alice["url"] == "https://github.com/alice/cool-project"
        assert alice["primary_language"] == "Python"
        assert alice["description"] == "A cool project for agents & tools 🚀"
        assert alice["period_stars"] == 5000
        assert alice["total_stars"] == 42000

    def test_missing_language_and_description(self):
        bob = parse_trending_page(SAMPLE_HTML)[1]

        assert bob["primary_language"] == "Unknown"
        assert bob["description"] == ""
        assert bob["period_stars"] == 812
        assert bob["total_stars"] == 950

    def test_whitespace_singular_star_and_large_counts(self):
        carol = parse_trending_page(SAMPLE_HTML)[2]

        assert carol["description"] == "Fast thing in Rust"
        assert carol["period_stars"] == 1
        assert carol["total_stars"] == 1204311

    def test_unrecognized_markup_yields_nothing(self):
        assert parse_trending_page("<html><body><div>No trending repositories</div></body></html>") == []


class TestFetchTrending:
    def test_returns_up_to_limit_and_sends_user_agent(self):
        mock_open = MagicMock(return_value=_mock_html_urlopen(_page_with(25)))
        with patch("src.fetch.urllib.request.urlopen", mock_open):
            repos = fetch_trending(limit=50)

        assert len(repos) == 25
        assert repos[0]["repo_name"] == "owner0/repo0"
        request = mock_open.call_args.args[0]
        assert request.full_url == "https://github.com/trending?since=monthly"
        assert "github-trending-rss" in request.get_header("User-agent")

    def test_limit_applied(self):
        with patch("src.fetch.urllib.request.urlopen", return_value=_mock_html_urlopen(_page_with(25))):
            assert len(fetch_trending(limit=5)) == 5

    def test_too_few_repos_raises(self):
        with patch("src.fetch.urllib.request.urlopen", return_value=_mock_html_urlopen(SAMPLE_HTML)):
            with pytest.raises(ValueError, match="Only 3 repos parsed"):
                fetch_trending()

    def test_changed_markup_raises(self):
        with patch("src.fetch.urllib.request.urlopen", return_value=_mock_html_urlopen("<html></html>")):
            with pytest.raises(ValueError, match="Only 0 repos parsed"):
                fetch_trending()


class TestEnrichWithGithub:
    def test_enrichment_adds_fields(self):
        repos = [{"repo_name": "alice/cool-project", "period_stars": 5000}]
        gh_response = {
            "stargazers_count": 42000,
            "license": {"spdx_id": "MIT", "name": "MIT License"},
        }

        with patch("src.fetch._github_get", return_value=gh_response):
            enriched = enrich_with_github(repos, token="fake")

        assert enriched[0]["license"] == "MIT"
        assert enriched[0]["total_stars"] == 42000

    def test_fallback_on_failure(self):
        repos = [{"repo_name": "alice/cool-project", "period_stars": 5000}]

        with patch("src.fetch._github_get", side_effect=Exception("API error")):
            enriched = enrich_with_github(repos, token="fake")

        assert enriched[0]["license"] == "Unknown"
        assert enriched[0]["total_stars"] == 5000

    def test_noassertion_becomes_unknown(self):
        repos = [{"repo_name": "alice/cool-project", "period_stars": 5000}]
        gh_response = {
            "stargazers_count": 10000,
            "license": {"spdx_id": "NOASSERTION", "name": "Other"},
        }

        with patch("src.fetch._github_get", return_value=gh_response):
            enriched = enrich_with_github(repos, token="fake")

        assert enriched[0]["license"] == "Unknown"

    def test_null_license(self):
        repos = [{"repo_name": "alice/cool-project", "period_stars": 5000}]
        gh_response = {"stargazers_count": 10000, "license": None}

        with patch("src.fetch._github_get", return_value=gh_response):
            enriched = enrich_with_github(repos, token="fake")

        assert enriched[0]["license"] == "Unknown"

    def test_fallback_uses_trending_page_total(self):
        repos = [{"repo_name": "alice/cool-project", "period_stars": 5000, "total_stars": 42000}]

        with patch("src.fetch._github_get", side_effect=Exception("API down")):
            enriched = enrich_with_github(repos, token="fake")

        assert enriched[0]["total_stars"] == 42000
