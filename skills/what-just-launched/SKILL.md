---
name: what-just-launched
description: Discover and synthesize recently launched products across launch platforms, product directories, community/news sources, social/video feedback sources, and web search. Use when the user asks what just launched, what new products appeared recently, what new apps or AI products are emerging, or wants launch signals from sources such as Product Hunt, Peerlist Launchpad, BetaList, Microlaunch, Uneed, Fazier, Hacker News, Reddit, X/Twitter, YouTube, and web search.
---

# What Just Launched

## Quick Start

Use this skill for product discovery and product feedback research. Prefer the bundled engine before ad hoc browsing:

```bash
python scripts/just-launched.py "AI video editor" --mode all --days 30 --market us
```

For explicit date windows, use `--since` and `--until`:

```bash
python scripts/just-launched.py "new AI products" --mode discovery --since 2026-07-01 --until 2026-07-06 --filter-launch-date
```

Run a source check before important research:

```bash
python scripts/just-launched.py --preflight
```

For a fuller setup report:

```bash
python scripts/just-launched.py --diagnose
```

API keys can live in environment variables or `~/.config/what-just-launched/.env`. The legacy `~/.config/product-scout/.env` path is still supported as a fallback. Append keys without editing source:

```bash
python scripts/just-launched.py --write-config REDDIT_USER_AGENT="linux:what-just-launched:0.1.0 (by /u/example)"
```

The engine emits normalized JSON. Use its `preflight`, `errors`, and `results` fields as evidence, then synthesize a concise product intelligence brief for the user.

## Workflow

1. Parse the user's intent:
   - `discovery`: find new or trending products in a category.
   - `feedback`: find what users are saying about a product, competitor, or category.
   - `all`: combine product discovery and feedback.
2. Choose a time window. Default to `--days 30` unless the user asks for today, this week, last 7 days, etc.
3. Choose a market. Default to `--market us` unless the user names another country or region.
4. For "new product", "new app", "recent launch", or "上线日期" requests, add `--filter-launch-date` so old high-rating apps do not dominate.
5. Run `scripts/just-launched.py`.
6. Separate evidence from availability:
   - A source in `results` was actually queried.
   - A source in `missing_config` was not queried.
   - A source in `errors` failed and should not be treated as negative evidence.
7. Write the answer with source-level caveats when important sources were unavailable.

## Time Semantics

The top-level `time_range` is the search window. `launch_date` is the product's own launch or first release date when the source exposes it. `first_seen_at` is when the skill first saw the product in a chart/source. `evidence_published_at` is the evidence page, post, video, chart, or discussion date. `product_launch_date` and `published_at` remain as backward-compatible aliases.

Use `date_confidence` and `ranking.launch_date_confidence` carefully. Trending pages often expose trend dates, not true launch dates, so label those as "date not verified" when they matter.

Uneed uses completed weekly archives first, the current week's daily ladders, and historical daily ladders only when weekly results do not fill the requested limit. Weekly launch dates are inferred from each product's earliest vote timestamp and are less certain than daily ladder dates.

When `--filter-launch-date` is active, sources with known launch dates keep only products whose `product_launch_date` is inside `time_range`. Sources without a reliable launch date may still return results; label those as "date not verified" if they affect the conclusion.

## Ranking Semantics

Use `ranking.final_score` for final ordering. Treat `score` as a raw source-local signal only; raw counters from different platforms are not comparable.

The engine normalizes within each source, deduplicates by normalized URL/title, then uses weighted reciprocal rank fusion. Prefer results with strong `ranking.freshness`, direct `launch_date_confidence`, and multiple `matched_sources` when explaining why a product is notable.

Use `products` as the primary product discovery view. Order products by `product_score`, and use `score_breakdown` plus `rank_reasons` to explain why a product appears. Use `products[].community_feedback` for feedback already matched to a product. Use top-level `product_data` and `community_feedback` as source-level evidence partitions, including unmatched evidence. Treat `results` as a backward-compatible mixed ranked list.

## Source Routing

For product discovery, use:

```text
Product Hunt, Peerlist Launchpad, BetaList, Microlaunch, Uneed, Fazier
```

For user feedback, use:

```text
Reddit, Reddit Public JSON, Hacker News, Web Search,
GitHub Issues, Stack Exchange, Lobsters, X / Twitter, YouTube
```

Use `--sources` only when the user names specific sources or when a narrow source set is clearly better:

```bash
python scripts/just-launched.py "Cursor" --mode feedback --sources reddit,hacker_news,github_issues --days 30
```

Prefer split source routing when the task needs both product discovery and feedback:

```bash
python scripts/just-launched.py "AI coding tools" --mode all --product-sources product_hunt,uneed,fazier --feedback-sources web,reddit,hacker_news --days 7
```

## Safety And Reliability

Do not scrape Reddit HTML from server IPs. Reddit should use OAuth credentials and a unique descriptive User-Agent. The script keeps public Reddit JSON disabled unless `PRODUCT_SCOUT_ALLOW_REDDIT_PUBLIC_JSON=true` is explicitly set.

For X/Twitter, prefer server-safe keys (`XAI_API_KEY` or `XQUIK_API_KEY`) on servers. Browser cookie access (`FROM_BROWSER=auto` or `AUTH_TOKEN` + `CT0`) is for local/user-consented use only. Never write cookies into the skill files.

`XQUIK_API_KEY` runs through the built-in Xquik adapter. For browser-cookie or xAI search, set `PRODUCT_SCOUT_X_ADAPTER_COMMAND` to a local command that reads a JSON request from stdin and returns JSON items on stdout.

For YouTube, use `YOUTUBE_API_KEY` for video discovery. Use `yt-dlp` only as an optional transcript helper, and treat throttling or bot gates as source degradation.

For web search, use configured API providers (`BRAVE_API_KEY` or `BRAVE_SEARCH_API_KEY`, `SERPAPI_API_KEY`, `TAVILY_API_KEY`). Treat web search as community/news evidence, not as a primary product discovery source. Use Firecrawl only as a fallback webpage parser for page-based product sources such as BetaList, Microlaunch, Uneed, and Fazier, not as a web-search provider. Prefer structured APIs or feeds, then direct HTML, then Firecrawl, and reserve browser-context retrieval for the final fallback.

## Output Brief

For discovery tasks, include:

```text
Top products
What each product does
Source and signal
Why it is worth watching
Links
```

For feedback tasks, include:

```text
Main praise
Main complaints
Repeated user needs
Credibility of the signals
Links to the strongest evidence
```

For combined research, include:

```text
Market snapshot
Notable products
User feedback themes
Opportunity gaps
Follow-up sources to configure
```

Use `community_feedback_summary` for broad user-feedback themes, and `products[].feedback_summary` when explaining feedback tied to one product.

For web-search evidence, inspect `signals.result_type`, `signals.feedback_likelihood`, and `signals.date_verified`. Treat low-likelihood official pages, launch listings, listicles, and press releases as market evidence rather than user feedback.

Read `references/source_strategy.md` when choosing sources or explaining missing coverage. Read `references/configuration.md` when setting up keys. Read `references/output_contract.md` when changing scripts or building downstream tooling against the JSON output.

When changing source coverage, keep product/app/repository adapters under `scripts/just_launched/sources/product_data/`, keep community/comment feedback adapters under `scripts/just_launched/sources/community_feedback/`, and register source ids, method names, source types, and mode membership in `scripts/just_launched/sources/registry.py`.
