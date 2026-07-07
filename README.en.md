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

The script entrypoint stays thin; the implementation lives in a small Python package:

```text
skills/what-just-launched/scripts/just_launched/
├── cli.py              # CLI arguments, config writing, JSON output
├── common.py           # Config, dates, HTTP, normalized item helpers
├── engine.py           # Search orchestration, no concrete source logic
├── ranking.py          # Deduplication, normalized scoring, weighted RRF fusion
├── sources/
│   ├── registry.py     # source ids, mode groups, method mapping
│   ├── product_hunt.py
│   ├── hacker_news.py
│   ├── web_search.py
│   ├── github.py
│   ├── app_stores.py
│   ├── directories.py
│   └── feedback.py
└── __init__.py
```

To add a source, create or extend an adapter under `sources/`, then register its source id, method name, and supported modes in `sources/registry.py`.

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

## Install Into Other Agent Tools

This repository uses the common Agent Skills shape:

```text
skills/what-just-launched/SKILL.md
skills/what-just-launched/scripts/just-launched.py
skills/what-just-launched/scripts/just_launched/
skills/what-just-launched/references/
```

Most tools that support Agent Skills can load a folder that contains `SKILL.md`, scripts, and references. The main differences are the skill directory and whether the tool requires an allowlist.

### Claude Code

Claude Code officially supports skills. A typical install is:

```bash
mkdir -p ~/.claude/skills
cp -R skills/what-just-launched ~/.claude/skills/
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills"
Copy-Item -Recurse -Force "skills\what-just-launched" "$env:USERPROFILE\.claude\skills\"
```

Then ask Claude Code:

```text
Use what-just-launched to find new AI products from the last 7 days.
```

If Claude Code does not discover the skill immediately, restart Claude Code or inspect the `/skills` / slash command interface.

Reference: Claude Code skills documentation: <https://code.claude.com/docs/en/skills>

### Kimi Code CLI

Kimi Code CLI supports Agent Skills. Start with the shared `.agents/skills/` directory:

```bash
mkdir -p .agents/skills
cp -R skills/what-just-launched .agents/skills/
```

For project-local use, the expected shape is:

```text
.agents/skills/what-just-launched/SKILL.md
```

Then ask Kimi Code:

```text
Use what-just-launched to discover new mobile apps launched this week.
```

Reference: Kimi Code CLI Agent Skills documentation: <https://moonshotai.github.io/kimi-cli/en/customization/skills.html>

### Cursor

Cursor supports Agent Skills and can discover skills from project-level or personal skill directories. Prefer project-level installation when you want the skill to travel with a repository.

Project-level install:

```bash
mkdir -p .cursor/skills
cp -R skills/what-just-launched .cursor/skills/
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path ".cursor\skills"
Copy-Item -Recurse -Force "skills\what-just-launched" ".cursor\skills\"
```

Personal installation can use your Cursor user configuration directory; check your current Cursor version for the exact path. After installation, ask Cursor Agent Chat:

```text
Use what-just-launched to find new AI agent products launched in the last 7 days.
```

Cursor uses the `description` field in `SKILL.md` to decide when a skill is relevant. If automatic selection does not trigger, explicitly say `use what-just-launched skill`.

Reference: Cursor Agent Skills documentation: <https://cursor.com/docs/skills>

### OpenCode

OpenCode has native Agent Skills support. It can discover `SKILL.md` definitions from your repo or home directory and load them on demand through the built-in skill tool. For project-level usage, install into `.agents/skills/`:

```bash
mkdir -p .agents/skills
cp -R skills/what-just-launched .agents/skills/
```

You can also use a user-level skills directory, depending on your OpenCode configuration. To make discovery more explicit, add a project instruction:

```text
When the task is about finding recently launched products, use .agents/skills/what-just-launched.
```

Then ask OpenCode:

```text
Use the what-just-launched skill to list new AI products launched this week.
```

Reference: OpenCode Agent Skills documentation: <https://opencode.ai/docs/skills/>

### OpenClaw

OpenClaw supports skills configuration and allowlists. Put the skill in a directory that OpenClaw scans, then allow `what-just-launched` in the OpenClaw skills config if your setup uses allowlists.

Example structure:

```text
~/.openclaw/skills/what-just-launched/SKILL.md
```

Copy example:

```bash
mkdir -p ~/.openclaw/skills
cp -R skills/what-just-launched ~/.openclaw/skills/
```

If your OpenClaw instance uses an allowlist, add `what-just-launched`. OpenClaw's docs note that allowlists are visibility and loading filters, not shell authorization boundaries, so you should still review third-party skill code before running it.

Reference: OpenClaw skills config documentation: <https://docs.openclaw.ai/tools/skills-config>

### Hermes Agent

Hermes Agent is more profile/workspace oriented. A practical setup is to copy this skill into the current Hermes workspace or agent resources directory, then reference it from your Hermes workspace/profile instructions.

Recommended structure:

```text
<your-hermes-workspace>/skills/what-just-launched/SKILL.md
```

Example Hermes workspace/profile note:

```text
When asked to discover recently launched products, use the skill at skills/what-just-launched.
Run scripts/just-launched.py for structured launch search results.
```

Reference: Hermes Agent documentation: <https://hermes-agent.nousresearch.com/docs/>

### Shared Agent Skills Directory

Some tools use a shared directory:

```text
.agents/skills/
```

If your agent supports this convention, copy the skill there:

```bash
mkdir -p .agents/skills
cp -R skills/what-just-launched .agents/skills/
```

This is useful for Kimi Code, some IDE agents, cloud coding agents, and tools that support the open Agent Skills structure. If auto-discovery does not work, add an explicit project instruction:

```text
Use .agents/skills/what-just-launched when the task is about discovering recently launched products.
```

### Plain CLI Fallback

If an agent tool does not support skills yet, use the engine as a normal CLI:

```bash
cd skills/what-just-launched
python scripts/just-launched.py "new AI products" --mode discovery --days 7 --market us
```

Then pass the JSON output back to the agent for summarization. This is the most portable and easiest-to-debug mode.

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
  "ranking_model": {
    "name": "source-normalized-weighted-rrf",
    "rrf_k": 60
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
      },
      "ranking": {
        "final_score": 0.812345,
        "matched_sources": ["hacker_news"],
        "launch_date_confidence": "evidence_date_only"
      }
    }
  ]
}
```

Use `ranking.final_score` for ordering. `score` is the source-local raw score and is not comparable across platforms.

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
