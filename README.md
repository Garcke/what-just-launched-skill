# What Just Launched

![What Just Launched](assets/what-just-launched-wordmark.svg)

Discover recently launched products, apps, AI tools, startup launches, and early market signals from product platforms, developer communities, app stores, and web search.

## Install

```bash
npx what-just-launched install
```

This npm installer removes the need to type `Garcke/what-just-launched-skill`.

Optional: target one agent.

```bash
npx what-just-launched install --agent claude-code
```

GitHub repository install is still supported:

```bash
npx skills add Garcke/what-just-launched-skill -g
```

## Configure

Keys are optional, but Product Hunt and web search are much better with them:

```bash
python scripts/just-launched.py --write-config PRODUCT_HUNT_TOKEN=<product_hunt_token>
python scripts/just-launched.py --write-config SERPAPI_API_KEY=<serpapi_key>
python scripts/just-launched.py --write-config TAVILY_API_KEY=<tavily_key>
python scripts/just-launched.py --write-config FIRECRAWL_API_KEY=<firecrawl_key>
```

Run a setup check:

```bash
npx what-just-launched doctor
```

## Use

```bash
npx what-just-launched run "new AI products" --mode discovery --days 7 --market us
```

Strict launch-date window:

```bash
npx what-just-launched run "new AI products" --mode discovery --since 2026-07-01 --until 2026-07-06 --filter-launch-date
```

## Sources

- Product discovery: Product Hunt, BetaList, Microlaunch, Uneed, Fazier.
- Feedback and news evidence: Reddit, Hacker News, GitHub Issues, Stack Exchange, Lobsters, X/Twitter, YouTube, Brave, SerpApi, Tavily.

## Documentation

- [English documentation](README.en.md)
- [中文文档](README.zh-CN.md)

Do not commit API keys, browser cookies, or `.env` files.
