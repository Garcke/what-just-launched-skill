# What Just Launched Source Strategy

## Product Discovery Sources

Use these eight sources in the first version:

| Source | Use For | Access |
|---|---|---|
| Product Hunt | SaaS, AI tools, indie products, launches | `PRODUCT_HUNT_TOKEN` for GraphQL |
| AppPark | App Store / Google Play style charts and categories | Public endpoint with browser User-Agent |
| Hacker News | developer products, Show HN, technical launches | HN Algolia API |
| GitHub Trending | open-source and developer-tool momentum | Public GitHub Trending page |
| Apple RSS / iTunes Search | iOS app charts and metadata | Official Apple public APIs |
| Google Play / AppBrain | Android app discovery fallback | AppBrain page search; upgrade later to Google Play scraper |
| BetaList | early-stage startups and waitlists | Public pages, low request volume |
| There's An AI For That | AI tool directories and task-specific tools | Public pages, low request volume |

## User Feedback Sources

Use these five feedback sources:

| Source | Use For | Access |
|---|---|---|
| Reddit | real user discussions, complaints, comparisons | OAuth first; public JSON only by explicit opt-in |
| X / Twitter | launch reactions, founder/user chatter, fast-moving sentiment | `XAI_API_KEY`, `XQUIK_API_KEY`, browser cookies, or manual cookies |
| YouTube | reviews, tutorials, launch videos, comments | `YOUTUBE_API_KEY`; optional `yt-dlp` transcripts |
| Hacker News | technical feedback and developer skepticism | HN Algolia API |
| Web Search | official posts, reviews, comparisons, fallback evidence | Brave, Exa, Serper, Tavily, or DuckDuckGo low-volume fallback |

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
sources/community_feedback/    community discussion, comments, videos, web feedback
sources/registry.py            source id, method name, source type, mode membership
common.py                      shared HTTP/date/item helpers
engine.py                      orchestration only
```

`product_data` sources answer "what exists or launched?".

`community_feedback` sources answer "what are people saying about it?".

Some platforms can serve both purposes. For example, Hacker News can surface Show HN launches and also provide developer reactions. Put the adapter where its evidence is primarily interpreted, then register it for every mode it should participate in.

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
