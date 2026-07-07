# What Just Launched Skill

`what-just-launched` is a Codex skill for discovering recently launched products. It is intentionally focused on one question:

```text
What just launched recently, and is it worth watching?
```

The skill gathers launch and early-market signals from product launch platforms, app stores, developer communities, web search, and feedback sources, then emits normalized JSON that Codex can turn into a concise product briefing.

## What It Is For

- Discover new AI products, apps, SaaS tools, developer tools, open-source projects, and startups from the last 7 or 30 days.
- Track recent launches in a category such as AI agents, AI video tools, mobile apps, or developer tooling.
- Inspect early traction signals such as Hacker News points, GitHub stars, App Store ratings, web mentions, and review pages.
- Collect early feedback from Reddit, X/Twitter, YouTube, Hacker News, and web reviews.
- Generate launch briefings, watchlists, and opportunity notes.

## Skill Location

```text
skills/what-just-launched
```

Main script:

```text
skills/what-just-launched/scripts/just-launched.py
```

## Sources

### Product Discovery Sources

| Source | Use For | Access |
|---|---|---|
| Product Hunt | SaaS, AI tools, indie products, launches | `PRODUCT_HUNT_TOKEN` |
| AppPark | App Store / Google Play style charts and category rankings | Public endpoint with browser User-Agent |
| Hacker News | Show HN, Launch HN, developer products | HN Algolia API |
| GitHub Trending / Search | Open-source projects and developer tools | GitHub pages/API |
| Apple RSS / iTunes Search | iOS app charts and app metadata | Apple public APIs |
| Google Play / AppBrain | Android app discovery fallback | AppBrain page search |
| BetaList | Early-stage startups and waitlists | Public pages, low-volume access |
| AI directories | AI product directories and niche tools | Public pages, low-volume access |

### Feedback Sources

| Source | Use For | Access |
|---|---|---|
| Reddit | Real user discussions, complaints, comparisons | OAuth first; HTML scraping disabled by default |
| X / Twitter | Launch reactions and fast-moving sentiment | `XQUIK_API_KEY` or external adapter |
| YouTube | Reviews, tutorials, and comments | `YOUTUBE_API_KEY` |
| Hacker News | Developer feedback and skepticism | HN Algolia API |
| Web Search | Official pages, reviews, comparisons, launch lists | Tavily / Brave / Exa / Serper / DuckDuckGo |

## Install Into Codex

Clone the repository and copy the skill into your Codex skills directory:

```bash
git clone https://github.com/Garcke/what-just-launched-skill.git
mkdir -p ~/.codex/skills
cp -R what-just-launched-skill/skills/what-just-launched ~/.codex/skills/
```

Windows PowerShell:

```powershell
git clone https://github.com/Garcke/what-just-launched-skill.git
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.codex\skills"
Copy-Item -Recurse -Force "what-just-launched-skill\skills\what-just-launched" "$env:USERPROFILE\.codex\skills\"
```

## Quick Start

From the skill directory:

```bash
cd skills/what-just-launched
```

Find new AI products from the last 7 days:

```bash
python scripts/just-launched.py "new AI products" --mode discovery --days 7 --market us
```

Find new mobile apps from the last 30 days:

```bash
python scripts/just-launched.py "new mobile apps" --mode discovery --days 30 --market us
```

Use an explicit date window and filter by product launch date:

```bash
python scripts/just-launched.py "new AI products" --mode discovery --since 2026-07-01 --until 2026-07-06 --filter-launch-date
```

Research user feedback for a product:

```bash
python scripts/just-launched.py "Cursor AI reviews" --mode feedback --days 30 --sources web,hacker_news
```

Check source availability:

```bash
python scripts/just-launched.py --preflight
```

Print a detailed setup report:

```bash
python scripts/just-launched.py --diagnose
```

## Common Options

| Option | Description |
|---|---|
| `query` | Search query, for example `"new AI products"` |
| `--mode discovery` | Discover recently launched products |
| `--mode feedback` | Collect feedback about a product or category |
| `--mode all` | Combine product discovery and feedback |
| `--days 7` | Search the last 7 days |
| `--since YYYY-MM-DD` | Start date |
| `--until YYYY-MM-DD` | End date |
| `--filter-launch-date` | Keep only products whose known launch date is inside the time window |
| `--market us` | Market/country code, such as `us`, `jp`, or `cn` |
| `--sources web,hacker_news` | Restrict source set |
| `--limit 20` | Maximum result count |
| `--include-raw` | Include raw source payloads for debugging |

## Time Semantics

The output separates three time concepts:

```text
time_range           The search window
published_at         The date of the evidence page, post, video, or discussion
product_launch_date  The product's launch or first release date when available
```

For new-product discovery, prefer:

```bash
--filter-launch-date
```

This prevents older high-rating app store products from dominating a query that is supposed to surface recent launches.

## Configuration

Do not commit secrets. Provide API keys through environment variables or:

```text
~/.config/what-just-launched/.env
```

The script reads environment variables first, then this `.env` file. It also supports the legacy path:

```text
~/.config/product-scout/.env
```

Append config values:

```bash
python scripts/just-launched.py --write-config TAVILY_API_KEY=your_key_here
python scripts/just-launched.py --write-config PRODUCT_SCOUT_WEB_PROVIDERS=tavily,duckduckgo,brave,exa
```

Recommended configuration:

```bash
# Product Hunt
PRODUCT_HUNT_TOKEN=

# Reddit OAuth. Do not scrape Reddit HTML from server IPs.
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=linux:what-just-launched:0.1.0 (by /u/your_username)

# X / Twitter
XQUIK_API_KEY=
XAI_API_KEY=
PRODUCT_SCOUT_X_ADAPTER_COMMAND=

# YouTube
YOUTUBE_API_KEY=

# Web Search
PRODUCT_SCOUT_WEB_PROVIDERS=tavily,duckduckgo,brave,exa
TAVILY_API_KEY=
BRAVE_API_KEY=
EXA_API_KEY=
SERPER_API_KEY=
```

## Web Search Providers

Supported providers:

```text
brave,exa,serper,tavily,duckduckgo
```

Suggested practical order:

```text
tavily,duckduckgo,brave,exa
```

DuckDuckGo requires no key and is useful as a low-volume fallback. Do not use it for high-concurrency scraping.

## Security Notes

- Do not commit `.env`, API keys, browser cookies, or GitHub tokens.
- Reddit should use OAuth. Avoid direct Reddit HTML scraping on servers to reduce 403/IP risk.
- X/Twitter cookie access is for local, user-consented flows only. Never save cookies in the repository.
- If a token appears in chat or logs, revoke it and generate a new one.

## Output Shape

The script emits JSON:

```json
{
  "query": "new AI products",
  "mode": "discovery",
  "market": "us",
  "days": 7,
  "time_range": {
    "since": "2026-06-30",
    "until": "2026-07-06"
  },
  "results": [
    {
      "source": "hacker_news",
      "kind": "post",
      "title": "Launch HN: Example",
      "url": "https://example.com",
      "summary": "Short evidence text",
      "published_at": "2026-07-02T15:11:20Z",
      "product_launch_date": "",
      "signals": {
        "points": 109,
        "comments": 70
      }
    }
  ]
}
```

## Current Limitations

- Product Hunt requires `PRODUCT_HUNT_TOKEN` for direct launch data.
- Unauthenticated GitHub requests can hit rate limits.
- App Store / iTunes results are useful for app metadata, but not every result is a recent launch.
- Web search may return launch directories or article pages; Codex should extract concrete products from them.
- Some sources prove discussion date, not the true product launch date.

## Useful Queries

```text
new AI products
new AI products launched this week
new mobile apps
new AI agents
new AI coding tools
new AI video tools
Show HN AI tool
Launch HN startup
Product Hunt AI agents
```

