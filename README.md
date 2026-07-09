# What Just Launched

![What Just Launched](assets/what-just-launched-wordmark.svg)

Discover recently launched products, apps, AI tools, startup launches, and early market signals from product platforms, developer communities, app stores, and web search.

Choose a language:

- [中文文档](README.zh-CN.md)
- [English documentation](README.en.md)

## Quick Example

```bash
python scripts/just-launched.py "new AI products" --mode discovery --days 7 --market us
```

For a strict launch-date window:

```bash
python scripts/just-launched.py "new AI products" --mode discovery --since 2026-07-01 --until 2026-07-06 --filter-launch-date
```

## Sources

- Product discovery: Product Hunt, Hacker News, GitHub Trending, Apple, Google Play/AppBrain, BetaList, Microlaunch, Uneed, Fazier.
- Feedback and market signals: Reddit, Hacker News, GitHub Issues, Stack Exchange, Lobsters, X/Twitter, YouTube, Brave, SerpApi, Tavily.

## Documentation

- [English documentation](README.en.md)
- [中文文档](README.zh-CN.md)

Do not commit API keys, browser cookies, or `.env` files.
