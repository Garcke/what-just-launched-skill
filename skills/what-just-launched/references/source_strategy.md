# What Just Launched Source Strategy

## Product Discovery Sources

Use these product discovery sources:

| Source | Use For | Access |
|---|---|---|
| Product Hunt | SaaS, AI tools, indie products, launches | `PRODUCT_HUNT_TOKEN` for GraphQL |
| Peerlist Launchpad | design, developer, AI, and indie product launches | Public weekly spotlight API with cursor pagination; raw HTTP may be blocked by Cloudflare |
| BetaList | early-stage startups and waitlists | Atom feed `https://feeds.feedburner.com/BetaList` for latest dated launches; HTML list/search/category pages as fallback |
| Microlaunch | indie products, SaaS, AI tools, developer products | Public page data merged with `https://nextjs-twitter-api.vercel.app/api/launches?channel=MicroLaunch&batch=YYYYMM`; match page `id` to API `product_id` |
| Uneed | indie products, SaaS, AI tools, launch pages | Public daily ladder API; optional Firecrawl fallback |
| Fazier | daily product launches and indie products | Next.js JSON data endpoint `/_next/data/{buildId}/index.json`, with page parsing fallback |

Candidate product sources to evaluate next:

| Source | Initial Quality | Notes |
|---|---|---|
| DevHunt | Medium-high for developer tools | Developer-tool directory with many tool pages. Good topical fit, but current page evidence does not expose reliable launch dates. Use as date-unverified discovery unless a dated endpoint is found. |
| Launching Next | Medium | New-startup directory with simple pages. Useful breadth, but weaker freshness and quality signals than Product Hunt, Uneed, Fazier, or Peerlist. |
| Tiny Startups | Unknown | Candidate launch board, but retrieval was unstable in testing. Re-test through Firecrawl before adding. |
| AI tool directories | Mixed | Futurepedia, Toolify, TAIAT, and similar sites are broad discovery sources, but often lack true launch dates and may rank SEO pages over actual launches. Use only with strong freshness evidence. |

## User Feedback Sources

Use these feedback sources:

| Source | Use For | Access |
|---|---|---|
| Reddit | real user discussions, complaints, comparisons | OAuth first; public JSON only by explicit opt-in |
| Reddit Public JSON | low-rate public Reddit fallback for local tests | explicit source id; can return 403 or bot gates |
| GitHub Issues | bugs, feature requests, migration pain, developer feedback | Public GitHub Search API |
| Stack Exchange | technical questions, integration pain, repeated needs | Public Stack Exchange API |
| Lobsters | developer-community discussions | explicit source id; public pages at low request volume |
| X / Twitter | launch reactions, founder/user chatter, fast-moving sentiment | `XAI_API_KEY`, `XQUIK_API_KEY`, browser cookies, or manual cookies |
| YouTube | reviews, tutorials, launch videos, comments | `YOUTUBE_API_KEY`; optional `yt-dlp` transcripts |
| Hacker News | technical feedback and developer skepticism | HN Algolia API |
| Web Search | official posts, reviews, comparisons, launch lists, news/search evidence; not a primary product discovery source | Brave, SerpApi, or Tavily |

## Reddit Safety Rules

Default to OAuth. Require:

```text
REDDIT_CLIENT_ID
REDDIT_CLIENT_SECRET
REDDIT_USER_AGENT
```

Use a descriptive User-Agent such as:

```text
linux:what-just-launched:0.1.0 (by /u/example)
```

Do not use generic Python/urllib/Java User-Agents. Respect Reddit rate-limit headers and avoid retry loops after 403, 429, or bot-gate responses. If OAuth is missing, report `missing_config` and use Web Search fallback for `site:reddit.com` style discovery rather than scraping Reddit pages.

## X / Twitter Access Rules

For servers, prefer:

```text
XAI_API_KEY
XQUIK_API_KEY
```

For local, user-consented runs, allow:

```text
FROM_BROWSER=auto
AUTH_TOKEN + CT0
```

Never save browser cookies in the skill folder, committed files, reports, or logs.

## Source Interpretation

`missing_config` means no search was performed for that source. Do not treat it as zero results.

`errors` means the source failed. Mention the failure if it materially affects the conclusion.

`results` means the source returned evidence. Rank by `ranking.final_score`; keep `score` only as the raw source-local signal.

The ranking model favors:

```text
source-local rank
fresh launch or evidence date
engagement normalized within the same source
source quality
duplicate confirmation across multiple sources
```

This prevents large raw counters, such as app rating counts or video views, from overwhelming smaller but more direct launch signals.

## Source Architecture

Keep product discovery data and community feedback collection separate.

Use this shape:

```text
sources/product_data/          app, product, repository, and directory adapters
sources/community_feedback/    community discussion, comments, videos, social feedback, and web-search adapters
sources/registry.py            source id, method name, source type, mode membership
common.py                      shared HTTP/date/item helpers
engine.py                      orchestration only
```

`product_data` sources answer "what exists or launched?".

`community_feedback` sources answer "what are people saying about it?".

Some platforms can serve both purposes, but keep the default routing conservative. For example, Hacker News can surface Show HN launches, but it is treated as community/news evidence rather than a primary product discovery source.

## Adding Sources

To add a product-data source:

1. Add an adapter under `sources/product_data/` that returns normalized `item(...)` dictionaries.
2. Register it in `PRODUCT_DATA_SPECS` with a stable source id, method name, and modes.
3. Add or adjust source weights in `ranking.py` when the source has different quality or rank reliability.
4. Add config keys to `preflight()` and `diagnose()` when the source needs credentials.

To add a community-feedback source:

1. Add an adapter under `sources/community_feedback/` that returns normalized `item(...)` dictionaries.
2. Register it in `COMMUNITY_FEEDBACK_SPECS` with a stable source id, method name, and modes.
3. Add or adjust source weights in `ranking.py` when the source has different quality or rank reliability.
4. Add config keys to `preflight()` and `diagnose()` when the source needs credentials.
