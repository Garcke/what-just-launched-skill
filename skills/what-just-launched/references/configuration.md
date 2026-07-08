# What Just Launched Configuration

What Just Launched reads environment variables first, then `~/.config/what-just-launched/.env`. It also falls back to the legacy `~/.config/product-scout/.env` if the new config file does not exist.

Use the script to append missing keys safely:

```bash
python scripts/just-launched.py --write-config KEY=VALUE
```

Do not store secrets in `SKILL.md`, source files, reports, or committed artifacts.

## Recommended `.env`

```bash
# Product discovery
PRODUCT_HUNT_TOKEN=

# Reddit, OAuth first. Avoid Reddit HTML scraping on servers.
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=linux:what-just-launched:0.1.0 (by /u/your_username)
PRODUCT_SCOUT_REDDIT_COMMENTS=true

# X / Twitter. Prefer XQUIK on servers; use external adapter for browser-cookie or xAI flows.
XQUIK_API_KEY=
XAI_API_KEY=
PRODUCT_SCOUT_X_ADAPTER_COMMAND=

# YouTube discovery
YOUTUBE_API_KEY=
PRODUCT_SCOUT_YOUTUBE_COMMENTS=false

# Web search
PRODUCT_SCOUT_WEB_PROVIDERS=serpapi,exa,tavily,duckduckgo
SERPAPI_API_KEY=
EXA_API_KEY=
TAVILY_API_KEY=
PRODUCT_SCOUT_DDG_REGION=
PRODUCT_SCOUT_DDG_DELAY=1.0
```

## X Adapter Command Contract

Set:

```bash
PRODUCT_SCOUT_X_ADAPTER_COMMAND=/path/to/x_adapter
```

The command receives JSON on stdin:

```json
{
  "query": "Cursor AI",
  "days": 30,
  "from_date": "2026-06-06",
  "to_date": "2026-07-06",
  "limit": 30
}
```

It should print either a list or an object with `items`:

```json
{
  "items": [
    {
      "title": "post title",
      "text": "post text",
      "url": "https://x.com/user/status/...",
      "date": "2026-07-06",
      "score": 42,
      "signals": {
        "likes": 10,
        "reposts": 2,
        "replies": 4
      }
    }
  ]
}
```

Use this for local, consented browser-cookie adapters or an xAI-backed adapter without changing the core code.

## Web Search Providers

Default order:

```text
serpapi,exa,tavily,duckduckgo
```

Provider behavior:

| Provider | Key | Notes |
|---|---|---|
| SerpApi | `SERPAPI_API_KEY` | Google-style search results API. |
| Exa | `EXA_API_KEY` | Good for agentic web search and page snippets. |
| Tavily | `TAVILY_API_KEY` | Search API designed for AI workflows. |
| DuckDuckGo | none | Free HTML fallback. Use low request volume only. |

Override the order:

```bash
PRODUCT_SCOUT_WEB_PROVIDERS=serpapi,tavily,exa,duckduckgo
```

DuckDuckGo settings:

```bash
PRODUCT_SCOUT_DDG_REGION=us-en
PRODUCT_SCOUT_DDG_DELAY=1.0
```

Region defaults are inferred from `--market` for common markets. The time filter follows `--days`: day, week, month, or year.
