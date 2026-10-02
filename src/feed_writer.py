"""Build RSS item XML and prepend to feed.xml."""

from __future__ import annotations

import re

# Inline styles matching the existing feed exactly
TABLE_STYLE = 'style="width:100%; border-collapse:collapse; font-family:sans-serif; font-size:14px;"'
ROW_STYLE = 'style="border-bottom:1px solid #eee;"'
NAME_CELL_STYLE = 'style="padding:8px 0;"'
META_CELL_STYLE = 'style="text-align:right; color:#888;"'
SUMMARY_CELL_STYLE = 'style="padding:0 0 12px; color:#555;"'


def _format_stars(count: int) -> str:
    """Format star count as human-readable (e.g., 42000 -> '42k')."""
    if count >= 1000:
        value = count / 1000
        if value == int(value):
            return f"{int(value)}k"
        return f"{value:.1f}k"
    return str(count)


def build_item_html(categories: dict[str, list], month_label: str) -> str:
    """Build HTML content for <content:encoded> CDATA.

    Generates an intro paragraph and HTML tables grouped by category,
    matching the exact style of the existing feed.
    """
    parts = []

    for cat_name, repos in categories.items():
        if not repos:
            continue

        parts.append(f"\n<h2>{cat_name}</h2>\n")
        parts.append(f"\n<table {TABLE_STYLE}>")

        for repo in repos:
            name = repo["repo_name"]
            url = repo.get("url", f"https://github.com/{name}")
            lang = repo.get("language", "Unknown")
            lic = repo.get("license", "Unknown")
            stars = repo.get("stars", "0")
            summary = repo.get("summary", "")

            parts.append(
                f'\n<tr {ROW_STYLE}>'
                f'<td {NAME_CELL_STYLE}><strong><a href="{url}">{name}</a></strong></td>'
                f'<td {META_CELL_STYLE}>{lang} \u00b7 {lic} \u00b7 {stars}</td></tr>'
            )
            parts.append(
                f'\n<tr><td colspan="2" {SUMMARY_CELL_STYLE}>{summary}</td></tr>'
            )

        parts.append("\n</table>\n")

    # Footer
    total = sum(len(repos) for repos in categories.values())
    parts.append(
        f'\n<hr>\n<p style="color:#999; font-size:12px; text-align:center;">'
        f"{total} repositories \u00b7 Source: GitHub Trending</p>"
    )

    return "".join(parts)


def build_item_xml(
    categories: dict[str, list],
    description: str,
    month_label: str,
    guid_month: str,
    pub_date: str,
) -> str:
    """Build a complete <item> XML string.

    Args:
        categories: dict mapping category name to list of repo dicts
        description: plain-text summary for <description>
        month_label: e.g., "March 2026"
        guid_month: e.g., "2026-03"
        pub_date: RFC 2822 date string
    """
    html = build_item_html(categories, month_label)

    return (
        f"    <item>\n"
        f"      <title>GitHub Trending Digest \u2014 {month_label}</title>\n"
        f"      <link>https://github.com/trending</link>\n"
        f"      <guid isPermaLink=\"false\">github-trending-{guid_month}</guid>\n"
        f"      <pubDate>{pub_date}</pubDate>\n"
        f"      <description>{description}</description>\n"
        f"      <content:encoded><![CDATA[\n{html}\n]]></content:encoded>\n"
        f"    </item>\n"
    )


def prepend_item_to_feed(feed_path: str, item_xml: str, build_date: str) -> None:
    """Insert a new item into feed.xml before existing items.

    Also updates <lastBuildDate> to build_date.
    """
    with open(feed_path) as f:
        content = f.read()

    # Update lastBuildDate
    content = re.sub(
        r"<lastBuildDate>.*?</lastBuildDate>",
        f"<lastBuildDate>{build_date}</lastBuildDate>",
        content,
    )

    # Insert new item before the first existing <item>, or before </channel>
    item_marker = content.find("<item>")
    if item_marker != -1:
        # Insert before first <item> with a blank line
        content = content[:item_marker] + item_xml + "\n" + content[item_marker:]
    else:
        # No existing items — insert before </channel>
        channel_end = content.find("</channel>")
        if channel_end == -1:
            raise ValueError("Cannot find </channel> in feed.xml")
        content = content[:channel_end] + item_xml + "\n" + content[channel_end:]

    with open(feed_path, "w") as f:
        f.write(content)


def update_landing_page(
    index_path: str,
    categories: dict[str, list],
    description: str,
    month_label: str,
) -> None:
    """Replace the digest section in index.html with the latest month's content."""
    html = build_item_html(categories, month_label)

    digest_content = (
        f'<h2 class="digest-title">GitHub Trending Digest — {month_label}</h2>\n'
        f'    <p class="digest-desc">{description}</p>\n'
        f"    {html}\n"
    )

    with open(index_path) as f:
        content = f.read()

    content = re.sub(
        r"<!-- DIGEST_START -->.*?<!-- DIGEST_END -->",
        f"<!-- DIGEST_START -->\n    {digest_content}    <!-- DIGEST_END -->",
        content,
        flags=re.DOTALL,
    )

    with open(index_path, "w") as f:
        f.write(content)
