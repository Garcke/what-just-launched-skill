# What Just Launched

`what-just-launched` is a product discovery engine for recently launched products. It answers one focused question:

```text
What just launched recently, and is it worth watching?
```

It gathers launch and early-market signals from product launch platforms, app stores, developer communities, community/news search, and feedback sources, then emits normalized JSON that agent tools can turn into a concise product briefing.

## Install

The recommended install path is the open Agent Skills CLI. It supports Codex, Claude Code, Cursor, OpenCode, Gemini CLI, Copilot, and many other compatible hosts.

```bash
npx skills add Garcke/what-just-launched-skill -g
```

`-g` installs globally for your user. Drop `-g` to install into the current project.

### Agent-Specific Install

Install only for Codex:

```bash
npx skills add Garcke/what-just-launched-skill -g -a codex
```

Install only for Claude Code:

```bash
npx skills add Garcke/what-just-launched-skill -g -a claude-code
```

Install only for Cursor:

```bash
npx skills add Garcke/what-just-launched-skill -g -a cursor
```

Install only for OpenCode:

```bash
npx skills add Garcke/what-just-launched-skill -g -a opencode
```

Install for multiple agents:

```bash
npx skills add Garcke/what-just-launched-skill -g -a codex -a cursor -a claude-code
```

List the skill before installing:

```bash
npx skills add Garcke/what-just-launched-skill --list
```

Update later:

```bash
npx skills update what-just-launched -g
```

List or remove:

```bash
npx skills list -g
npx skills remove what-just-launched -g
```

### Claude Code Prompt Install

If you want Claude Code to perform the install, paste this prompt into Claude Code:

```text
Install the Agent Skill from https://github.com/Garcke/what-just-launched-skill for Claude Code using:
npx skills add Garcke/what-just-launched-skill -g -a claude-code
Then run the skill's preflight or diagnose command and summarize which sources are configured.
```

If this project later becomes available in the Claude Code marketplace, prefer the marketplace command because it handles plugin-style updates. Until then, use `npx skills`.

### Manual Developer Install

Use this when editing the source locally:

```bash
git clone https://github.com/Garcke/what-just-launched-skill.git
cd what-just-launched-skill
```

For Codex:

```bash
mkdir -p ~/.codex/skills
cp -R skills/what-just-launched ~/.codex/skills/
```

For Claude Code:

```bash
mkdir -p ~/.claude/skills
cp -R skills/what-just-launched ~/.claude/skills/
```

Windows PowerShell example:

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.codex\skills"
Copy-Item -Recurse -Force "skills\what-just-launched" "$env:USERPROFILE\.codex\skills\"
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

### Minimal Setup

Some sources work without keys, including Hacker News, GitHub Trending, Apple public endpoints, Uneed, Fazier, Stack Exchange, and Lobsters.

Check what is available:

```bash
python scripts/just-launched.py --preflight
python scripts/just-launched.py --diagnose
```

### Recommended Keys

```bash
# Product discovery
python scripts/just-launched.py --write-config PRODUCT_HUNT_TOKEN=<product_hunt_token>

# Web search
python scripts/just-launched.py --write-config SERPAPI_API_KEY=<serpapi_key>
python scripts/just-launched.py --write-config TAVILY_API_KEY=<tavily_key>

# Optional page parsing helper for page-based product sources
python scripts/just-launched.py --write-config FIRECRAWL_API_KEY=<firecrawl_key>
```

### Full `.env` Template

```bash
# Product Hunt
PRODUCT_HUNT_TOKEN=
PRODUCT_SCOUT_PRODUCT_HUNT_TOPIC=

# Reddit OAuth
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=linux:what-just-launched:0.1.0 (by /u/your_username)
PRODUCT_SCOUT_REDDIT_COMMENTS=true

# X / Twitter
XQUIK_API_KEY=
XAI_API_KEY=
PRODUCT_SCOUT_X_ADAPTER_COMMAND=

# YouTube
YOUTUBE_API_KEY=
PRODUCT_SCOUT_YOUTUBE_COMMENTS=false

# Web Search
PRODUCT_SCOUT_WEB_PROVIDERS=brave,serpapi,tavily
BRAVE_API_KEY=
SERPAPI_API_KEY=
TAVILY_API_KEY=

# Page parsing helper
FIRECRAWL_API_KEY=
```

## Use

Find new AI products from the last 7 days:

```bash
python scripts/just-launched.py "new AI products" --mode discovery --days 7 --market us
```

Use an explicit date window and filter by product launch date:

```bash
python scripts/just-launched.py "new AI products" --mode discovery --since 2026-07-01 --until 2026-07-06 --filter-launch-date
```

Research user feedback for a product:

```bash
python scripts/just-launched.py "Cursor AI reviews" --mode feedback --days 30 --sources hacker_news,github_issues
```

Use split source routing:

```bash
python scripts/just-launched.py "AI coding tools" --mode all --product-sources product_hunt,github_trending,uneed,fazier --feedback-sources web,hacker_news,reddit --days 7
```

## Sources

### Product Discovery

| Source | Use For | Access |
|---|---|---|
| Product Hunt | SaaS, AI tools, indie products, launches | `PRODUCT_HUNT_TOKEN` |
| Hacker News | Show HN, Launch HN, developer products | HN Algolia API |
| GitHub Trending | Open-source projects and developer tools | Public page; optional Firecrawl parsing |
| Apple RSS / iTunes Search | iOS app charts and metadata | Apple public APIs |
| Google Play / AppBrain | Android app discovery fallback | AppBrain page search |
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
| Web Search | Reviews, comparisons, launch lists, news evidence | Brave / SerpApi / Tavily |

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

Every push to GitHub should be accompanied by a new version tag and GitHub Release. Use `vMAJOR.MINOR.PATCH`, for example `v1.8.2`.
