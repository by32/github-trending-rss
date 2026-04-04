"""Claude Sonnet editorial: categorize repos and write summaries."""

from __future__ import annotations

import json
import logging
import re
import time

import anthropic

logger = logging.getLogger(__name__)

CATEGORIES = [
    "AI / Machine Learning",
    "Developer Tools / Skills Ecosystem",
    "Web, Infrastructure, and Browser Automation",
    "Education and Research",
    "Data, OSINT, and Utilities",
]

SYSTEM_PROMPT = """\
You are a technical curator for a monthly GitHub Trending RSS digest.
You categorize repositories and write concise, factual summaries.
Return valid JSON only — no markdown fences, no commentary."""

USER_PROMPT_TEMPLATE = """\
Here are the top {count} trending GitHub repositories for {month_label}:

{repos_json}

Categorize each repository into exactly one of these categories:
{categories}

For each repository, write a 1-2 sentence summary highlighting what makes \
it notable this month. Include star velocity when remarkable.

Format star counts as human-readable (e.g., 42000 -> "42k").

Return JSON in this exact format:
{{
  "description": "2-3 sentence plain-text summary of the month's trends",
  "categories": {{
    "AI / Machine Learning": [
      {{"repo_name": "owner/name", "url": "https://github.com/owner/name",
       "language": "Python", "license": "MIT", "stars": "42k",
       "summary": "..."}}
    ]
  }}
}}

Only include categories that have at least one repository. Use the exact \
category names listed above."""


def build_prompt(repos: list[dict], month_label: str) -> str:
    """Build the user prompt with repo data embedded as JSON."""
    # Pass only the fields Claude needs
    slim_repos = [
        {
            "repo_name": r["repo_name"],
            "url": r["url"],
            "primary_language": r["primary_language"],
            "license": r.get("license", "Unknown"),
            "total_stars": r.get("total_stars", r.get("period_stars", 0)),
            "period_stars": r.get("period_stars", 0),
            "description": r.get("description", ""),
        }
        for r in repos
    ]
    categories_list = "\n".join(f"- {c}" for c in CATEGORIES)
    return USER_PROMPT_TEMPLATE.format(
        count=len(slim_repos),
        month_label=month_label,
        repos_json=json.dumps(slim_repos, indent=2),
        categories=categories_list,
    )


def _extract_json(text: str) -> str:
    """Strip markdown fences if Claude wraps JSON in them."""
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1)
    return text.strip()


def call_claude(prompt: str, api_key: str) -> dict:
    """Call Anthropic Messages API with Claude Sonnet and return parsed JSON.

    Retries up to 2 times with exponential backoff on API errors.
    """
    client = anthropic.Anthropic(api_key=api_key)
    delays = [5, 15]

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=16384,
                temperature=0.3,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = _extract_json(message.content[0].text)
            return json.loads(text)
        except json.JSONDecodeError:
            if attempt < 2:
                logger.warning("Claude returned invalid JSON, retrying with correction")
                prompt = prompt + "\n\nYour previous response was not valid JSON. Please return ONLY valid JSON."
                continue
            raise
        except anthropic.APIError as e:
            if attempt < 2:
                logger.warning("Anthropic API error (attempt %d): %s", attempt + 1, e)
                time.sleep(delays[attempt])
                continue
            raise

    raise RuntimeError("Unreachable")  # pragma: no cover


def parse_editorial_response(response: dict) -> tuple[dict[str, list], str]:
    """Parse Claude's JSON response into categories dict and description.

    Returns:
        (categories, description) where categories maps category name
        to a list of repo dicts with: repo_name, url, language, license,
        stars, summary.
    """
    description = response.get("description", "")
    categories = response.get("categories", {})

    if not categories:
        raise ValueError("Claude returned empty categories")

    return categories, description
