# What Just Launched

`what-just-launched` is a product discovery engine for recently launched products. It answers one focused question:

```text
What just launched recently, and is it worth watching?
```

It gathers launch and early-market signals from product launch platforms, app stores, developer communities, community/news search, and feedback sources, then emits normalized JSON that agent tools can turn into a concise product briefing.

## Install

Recommended install:

```bash
npx what-just-launched install
```

The npm installer installs the bundled skill into your local agent skill directory. By default it targets Codex.

Optional: target one agent.

```bash
npx what-just-launched install --agent claude-code
```

Replace `claude-code` with another supported target when needed: `codex`, `cursor`, `opencode`, `shared`, or `all`.

Run without installing:

```bash
npx what-just-launched run "new AI products" --mode discovery --days 7
```

GitHub repository install is still supported, but it requires `owner/repo`:

```bash
npx skills add Garcke/what-just-launched-skill -g
```

## Configuration

Do not commit secrets. Provide API keys through environment variables or:

```text
~/.config/what-just-launched/.env
```

The script reads environment variables first, then this `.env` file. It also supports the legacy path:

```text
~/.config/product-scout/.env
```

Append config values safely:

```bash
python scripts/just-launched.py --write-config KEY=VALUE
```

Minimal setup works without keys for Peerlist, BetaList, Microlaunch, Uneed, Fazier, Hacker News, Stack Exchange, and Lobsters. Peerlist may still require a browser-network context when Cloudflare blocks raw HTTP from the current IP.
Page-based product sources try Firecrawl when available. If `FIRECRAWL_API_KEY` is not configured, the engine tries Firecrawl keyless by default and falls back to direct HTML when keyless is blocked.

Check available sources:

```bash
python scripts/just-launched.py --preflight
npx what-just-launched doctor
```

Recommended keys:

```bash
python scripts/just-launched.py --write-config PRODUCT_HUNT_TOKEN=<product_hunt_token>
python scripts/just-launched.py --write-config SERPAPI_API_KEY=<serpapi_key>
python scripts/just-launched.py --write-config TAVILY_API_KEY=<tavily_key>
python scripts/just-launched.py --write-config FIRECRAWL_API_KEY=<firecrawl_key>
```

Full `.env` template:

```bash
PRODUCT_HUNT_TOKEN=
PRODUCT_SCOUT_PRODUCT_HUNT_TOPIC=

REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=linux:what-just-launched:0.1.0 (by /u/your_username)
PRODUCT_SCOUT_REDDIT_COMMENTS=true

XQUIK_API_KEY=
XAI_API_KEY=
PRODUCT_SCOUT_X_ADAPTER_COMMAND=

YOUTUBE_API_KEY=
PRODUCT_SCOUT_YOUTUBE_COMMENTS=false

PRODUCT_SCOUT_WEB_PROVIDERS=brave,serpapi,tavily
BRAVE_API_KEY=
SERPAPI_API_KEY=
TAVILY_API_KEY=
FIRECRAWL_API_KEY=
```

## Use

Find new AI products from the last 7 days:

```bash
npx what-just-launched run "new AI products" --mode discovery --days 7 --market us
```

Use an explicit date window and filter by product launch date:

```bash
npx what-just-launched run "new AI products" --mode discovery --since 2026-07-01 --until 2026-07-06 --filter-launch-date
```

Research user feedback for a product:

```bash
npx what-just-launched run "Cursor AI reviews" --mode feedback --days 30 --sources hacker_news,github_issues
```

Use split source routing:

```bash
npx what-just-launched run "AI coding tools" --mode all --product-sources product_hunt,uneed,fazier --feedback-sources web,hacker_news,reddit --days 7
```

## Sources

### Product Discovery

| Source | Use For | Access |
|---|---|---|
| Product Hunt | SaaS, AI tools, indie products, launches | `PRODUCT_HUNT_TOKEN` |
| Peerlist Launchpad | Design, developer, AI, and indie launches | Public weekly API; Cloudflare may block raw HTTP |
| BetaList | Early-stage startups and waitlists | Public pages; optional Firecrawl parsing |
| Microlaunch | Indie products, SaaS, AI tools | Public pages; optional Firecrawl parsing |
| Uneed | Indie products and launch pages | Public daily ladder API; optional Firecrawl fallback |
| Fazier | Daily launches and indie products | Public pages; optional Firecrawl parsing |

### Feedback And Market Signals

| Source | Use For | Access |
|---|---|---|
| Reddit | User discussions, complaints, comparisons | OAuth first |
| Reddit Public JSON | Local low-rate fallback | Explicitly enabled |
| GitHub Issues | Bugs, feature requests, developer feedback | Public GitHub Search API |
| Stack Exchange | Technical questions and integration pain | Public Stack Exchange API |
| Lobsters | Developer-community discussion | Public pages |
| X / Twitter | Launch reactions and social signals | `XQUIK_API_KEY` or adapter |
| YouTube | Reviews, tutorials, comments | `YOUTUBE_API_KEY` |
| Hacker News | Developer feedback and skepticism | HN Algolia API |
| Web Search | Reviews, comparisons, launch lists, news evidence; not a primary product source | Brave / SerpApi / Tavily |

## Output Shape

The script emits normalized JSON with:

```json
{
  "query": "new AI products",
  "mode": "discovery",
  "time_range": {
    "since": "2026-07-01",
    "until": "2026-07-07"
  },
  "products": [],
  "product_data": [],
  "community_feedback": [],
  "results": [],
  "preflight": [],
  "errors": []
}
```

Use `products` as the primary product discovery view. `product_data` contains source-level product evidence. `community_feedback` contains discussion, social, video, and web-search feedback evidence. `results` remains as a backward-compatible mixed ranked list.

## Security Notes

- Do not commit `.env`, API keys, browser cookies, or GitHub tokens.
- Reddit should use OAuth. Avoid direct Reddit HTML scraping on servers.
- X/Twitter cookie access is for local, user-consented flows only.
- If a token appears in chat or logs, revoke it and generate a new one.

## Release Rule

Every push to GitHub should be accompanied by a new version tag and GitHub Release. Use `vMAJOR.MINOR.PATCH`, for example `v1.8.4`.
