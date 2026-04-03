"""Tests for src/fetch module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.fetch import enrich_with_github, fetch_trending

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_urlopen(data: dict):
    """Create a mock for urllib.request.urlopen that returns JSON data."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestFetchTrending:
    def test_parse_response(self):
        sample = json.loads((FIXTURES / "sample_api_response.json").read_text())

        with patch("src.fetch.urllib.request.urlopen", return_value=_mock_urlopen(sample)):
            repos = fetch_trending(limit=5)

        assert len(repos) == 5
        assert repos[0]["repo_name"] == "alice/cool-project"
        assert repos[0]["url"] == "https://github.com/alice/cool-project"
        assert repos[0]["primary_language"] == "Python"
        assert repos[0]["period_stars"] == 5000

    def test_null_language_becomes_unknown(self):
        sample = json.loads((FIXTURES / "sample_api_response.json").read_text())

        with patch("src.fetch.urllib.request.urlopen", return_value=_mock_urlopen(sample)):
            repos = fetch_trending(limit=5)

        dave = repos[3]
        assert dave["repo_name"] == "dave/data-viz"
        assert dave["primary_language"] == "Unknown"

    def test_sorted_by_total_score(self):
        sample = json.loads((FIXTURES / "sample_api_response.json").read_text())

        with patch("src.fetch.urllib.request.urlopen", return_value=_mock_urlopen(sample)):
            repos = fetch_trending(limit=20)

        scores = [r["total_score"] for r in repos]
        assert scores == sorted(scores, reverse=True)

    def test_too_few_repos_raises(self):
        data = {"data": {"rows": [{"repo_name": "x/y", "stars": 1, "total_score": 1}]}}

        with patch("src.fetch.urllib.request.urlopen", return_value=_mock_urlopen(data)):
            with pytest.raises(ValueError, match="Only 1 repos returned"):
                fetch_trending()

    def test_empty_response_raises(self):
        data = {"data": {"rows": []}}

        with patch("src.fetch.urllib.request.urlopen", return_value=_mock_urlopen(data)):
            with pytest.raises(ValueError, match="Only 0 repos returned"):
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
