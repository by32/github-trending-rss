"""Tests for src/editorial module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.editorial import CATEGORIES, _extract_json, build_prompt, call_claude, parse_editorial_response

FIXTURES = Path(__file__).parent / "fixtures"


class TestBuildPrompt:
    def test_contains_repo_data(self):
        repos = [
            {
                "repo_name": "alice/cool-project",
                "url": "https://github.com/alice/cool-project",
                "primary_language": "Python",
                "license": "MIT",
                "total_stars": 42000,
                "period_stars": 5000,
                "description": "A cool project",
            }
        ]
        prompt = build_prompt(repos, "March 2026")

        assert "alice/cool-project" in prompt
        assert "March 2026" in prompt
        assert "Python" in prompt

    def test_contains_all_categories(self):
        prompt = build_prompt([], "March 2026")
        for cat in CATEGORIES:
            assert cat in prompt

    def test_month_label_in_prompt(self):
        prompt = build_prompt([], "April 2026")
        assert "April 2026" in prompt


class TestExtractJson:
    def test_plain_json(self):
        assert _extract_json('{"a": 1}') == '{"a": 1}'

    def test_markdown_fences(self):
        text = '```json\n{"a": 1}\n```'
        assert _extract_json(text) == '{"a": 1}'

    def test_markdown_fences_no_lang(self):
        text = '```\n{"a": 1}\n```'
        assert _extract_json(text) == '{"a": 1}'

    def test_fenced_json_parses(self):
        sample = json.loads((FIXTURES / "sample_claude_response.json").read_text())
        fenced = f"```json\n{json.dumps(sample)}\n```"
        result = json.loads(_extract_json(fenced))
        assert "categories" in result


class TestCallClaude:
    def test_success(self):
        sample = json.loads((FIXTURES / "sample_claude_response.json").read_text())
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(sample))]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("src.editorial.anthropic.Anthropic", return_value=mock_client):
            result = call_claude("test prompt", api_key="fake-key")

        assert "categories" in result
        assert "description" in result

    def test_strips_markdown_fences(self):
        sample = json.loads((FIXTURES / "sample_claude_response.json").read_text())
        fenced = f"```json\n{json.dumps(sample)}\n```"
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=fenced)]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("src.editorial.anthropic.Anthropic", return_value=mock_client):
            result = call_claude("test prompt", api_key="fake-key")

        assert "categories" in result

    def test_invalid_json_retries(self):
        sample = json.loads((FIXTURES / "sample_claude_response.json").read_text())

        bad_message = MagicMock()
        bad_message.content = [MagicMock(text="not json")]

        good_message = MagicMock()
        good_message.content = [MagicMock(text=json.dumps(sample))]

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [bad_message, good_message]

        with patch("src.editorial.anthropic.Anthropic", return_value=mock_client):
            result = call_claude("test prompt", api_key="fake-key")

        assert "categories" in result
        assert mock_client.messages.create.call_count == 2


class TestParseEditorialResponse:
    def test_valid_response(self):
        sample = json.loads((FIXTURES / "sample_claude_response.json").read_text())
        categories, description = parse_editorial_response(sample)

        assert "AI / Machine Learning" in categories
        assert len(categories["AI / Machine Learning"]) == 2
        assert description == "March 2026 was dominated by AI tooling and developer infrastructure improvements."

    def test_empty_categories_raises(self):
        with pytest.raises(ValueError, match="empty categories"):
            parse_editorial_response({"description": "test", "categories": {}})

    def test_missing_categories_raises(self):
        with pytest.raises(ValueError, match="empty categories"):
            parse_editorial_response({"description": "test"})

    def test_all_repos_have_required_fields(self):
        sample = json.loads((FIXTURES / "sample_claude_response.json").read_text())
        categories, _ = parse_editorial_response(sample)

        required = {"repo_name", "url", "language", "license", "stars", "summary"}
        for cat_repos in categories.values():
            for repo in cat_repos:
                assert required.issubset(repo.keys()), f"Missing fields in {repo['repo_name']}"
