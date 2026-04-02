# GitHub Trending Digest — RSS Feed

Monthly RSS feed of the top 50 trending GitHub repositories, auto-generated and hosted on GitHub Pages.

## Subscribe

Add this URL to your RSS reader:

```
https://byoungs.github.io/github-trending-rss/feed.xml
```

## How it works

A Claude scheduled task runs on the 1st of each month, researches the prior month's trending repos, and commits an updated `feed.xml` to this repo. GitHub Pages serves the feed.

## What's included

Each monthly item covers ~50 repos grouped by category (AI/ML, DevTools, Infrastructure, etc.) with repo links, language, license, star count, and a short summary.