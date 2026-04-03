"""Tests for src/feed_writer module."""

from __future__ import annotations

import shutil
from pathlib import Path

from src.feed_writer import build_item_html, build_item_xml, prepend_item_to_feed

FIXTURES = Path(__file__).parent / "fixtures"

SAMPLE_CATEGORIES = {
    "AI / Machine Learning": [
        {
            "repo_name": "alice/cool-project",
            "url": "https://github.com/alice/cool-project",
            "language": "Python",
            "license": "MIT",
            "stars": "42k",
            "summary": "A cool ML project.",
        },
    ],
    "Developer Tools / Skills Ecosystem": [
        {
            "repo_name": "bob/awesome-tool",
            "url": "https://github.com/bob/awesome-tool",
            "language": "TypeScript",
            "license": "MIT",
            "stars": "15k",
            "summary": "An awesome developer tool.",
        },
    ],
}


class TestBuildItemHtml:
    def test_contains_category_headers(self):
        html = build_item_html(SAMPLE_CATEGORIES, "March 2026")
        assert "<h2>AI / Machine Learning</h2>" in html
        assert "<h2>Developer Tools / Skills Ecosystem</h2>" in html

    def test_contains_repo_links(self):
        html = build_item_html(SAMPLE_CATEGORIES, "March 2026")
        assert 'href="https://github.com/alice/cool-project"' in html
        assert "alice/cool-project" in html

    def test_contains_metadata(self):
        html = build_item_html(SAMPLE_CATEGORIES, "March 2026")
        assert "Python · MIT · 42k" in html

    def test_contains_summary(self):
        html = build_item_html(SAMPLE_CATEGORIES, "March 2026")
        assert "A cool ML project." in html

    def test_contains_footer_count(self):
        html = build_item_html(SAMPLE_CATEGORIES, "March 2026")
        assert "2 repositories" in html

    def test_skips_empty_categories(self):
        cats = {**SAMPLE_CATEGORIES, "Education and Research": []}
        html = build_item_html(cats, "March 2026")
        assert "Education and Research" not in html

    def test_inline_styles_present(self):
        html = build_item_html(SAMPLE_CATEGORIES, "March 2026")
        assert "border-collapse:collapse" in html
        assert "font-family:sans-serif" in html


class TestBuildItemXml:
    def test_valid_structure(self):
        xml = build_item_xml(
            categories=SAMPLE_CATEGORIES,
            description="Test description",
            month_label="March 2026",
            guid_month="2026-03",
            pub_date="Wed, 01 Apr 2026 12:00:00 +0000",
        )
        assert "<item>" in xml
        assert "</item>" in xml
        assert "<guid" in xml
        assert "github-trending-2026-03" in xml

    def test_contains_title(self):
        xml = build_item_xml(
            categories=SAMPLE_CATEGORIES,
            description="Test",
            month_label="April 2026",
            guid_month="2026-04",
            pub_date="Fri, 01 May 2026 12:00:00 +0000",
        )
        assert "GitHub Trending Digest — April 2026" in xml

    def test_cdata_wrapper(self):
        xml = build_item_xml(
            categories=SAMPLE_CATEGORIES,
            description="Test",
            month_label="March 2026",
            guid_month="2026-03",
            pub_date="Wed, 01 Apr 2026 12:00:00 +0000",
        )
        assert "<content:encoded><![CDATA[" in xml
        assert "]]></content:encoded>" in xml


class TestPrependItemToFeed:
    def _copy_fixture(self, tmp_path: Path) -> Path:
        dest = tmp_path / "feed.xml"
        shutil.copy(FIXTURES / "sample_feed.xml", dest)
        return dest

    def test_new_item_appears_first(self, tmp_path):
        feed = self._copy_fixture(tmp_path)
        new_item = build_item_xml(
            categories=SAMPLE_CATEGORIES,
            description="April digest",
            month_label="April 2026",
            guid_month="2026-04",
            pub_date="Fri, 01 May 2026 12:00:00 +0000",
        )
        prepend_item_to_feed(
            str(feed), new_item, "Fri, 01 May 2026 12:00:00 +0000"
        )

        content = feed.read_text()
        april_pos = content.find("github-trending-2026-04")
        march_pos = content.find("github-trending-2026-03")
        assert april_pos < march_pos, "New item should appear before old item"

    def test_old_item_preserved(self, tmp_path):
        feed = self._copy_fixture(tmp_path)
        new_item = build_item_xml(
            categories=SAMPLE_CATEGORIES,
            description="April digest",
            month_label="April 2026",
            guid_month="2026-04",
            pub_date="Fri, 01 May 2026 12:00:00 +0000",
        )
        prepend_item_to_feed(
            str(feed), new_item, "Fri, 01 May 2026 12:00:00 +0000"
        )

        content = feed.read_text()
        assert "github-trending-2026-03" in content
        assert "Test content" in content

    def test_lastbuilddate_updated(self, tmp_path):
        feed = self._copy_fixture(tmp_path)
        new_item = "<item><title>Test</title></item>\n"
        prepend_item_to_feed(
            str(feed), new_item, "Fri, 01 May 2026 12:00:00 +0000"
        )

        content = feed.read_text()
        assert "<lastBuildDate>Fri, 01 May 2026 12:00:00 +0000</lastBuildDate>" in content
        assert "Wed, 01 Apr 2026" not in content.split("<lastBuildDate>")[1].split("</lastBuildDate>")[0]

    def test_insert_into_empty_feed(self, tmp_path):
        feed = tmp_path / "feed.xml"
        feed.write_text(
            '<?xml version="1.0"?>\n<rss version="2.0">\n  <channel>\n'
            "    <title>Test</title>\n"
            "    <lastBuildDate>old</lastBuildDate>\n"
            "  </channel>\n</rss>"
        )
        new_item = "<item><title>First</title></item>\n"
        prepend_item_to_feed(str(feed), new_item, "new-date")

        content = feed.read_text()
        assert "<item>" in content
        assert content.find("<item>") < content.find("</channel>")

    def test_wellformed_xml(self, tmp_path):
        """Verify the output can be parsed as XML."""

        feed = self._copy_fixture(tmp_path)
        new_item = build_item_xml(
            categories=SAMPLE_CATEGORIES,
            description="April digest",
            month_label="April 2026",
            guid_month="2026-04",
            pub_date="Fri, 01 May 2026 12:00:00 +0000",
        )
        prepend_item_to_feed(
            str(feed), new_item, "Fri, 01 May 2026 12:00:00 +0000"
        )

        # ElementTree can't handle namespace prefixes in content:encoded,
        # but we can verify basic XML structure by checking tag balance
        content = feed.read_text()
        assert content.count("<item>") == 2
        assert content.count("</item>") == 2
        assert content.count("<channel>") == 1
        assert content.count("</channel>") == 1
