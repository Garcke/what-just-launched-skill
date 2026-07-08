# What Just Launched Output Contract

The script emits UTF-8 JSON.

## Top-Level Object

```json
{
  "query": "AI video editor",
  "mode": "all",
  "market": "us",
  "days": 30,
  "selected_sources": ["product_hunt", "hacker_news", "web"],
  "time_range": {
    "since": "2026-06-07",
    "until": "2026-07-06"
  },
  "generated_at": "2026-07-06T00:00:00+00:00",
  "preflight": [],
  "errors": [],
  "ranking_model": {
    "name": "source-normalized-weighted-rrf",
    "rrf_k": 60,
    "formula": "0.35*rrf + 0.25*local_relevance + 0.15*freshness + 0.10*source_quality + 0.10*engagement + 0.05*source_diversity",
    "product_formula": "0.45*ranking_strength + 0.20*source_coverage + 0.15*feedback_strength + 0.10*evidence_depth + 0.10*launch_confidence"
  },
  "products": [],
  "product_data": [],
  "community_feedback": [],
  "community_feedback_summary": {},
  "results": []
}
```

## Preflight Entries

```json
{
  "source": "reddit",
  "status": "missing_config",
  "reason": "use REDDIT_CLIENT_ID..."
}
```

Statuses:

```text
available
missing_config
skipped_for_safety
unknown_source
http_403
http_429
error
```

## Result Entries

```json
{
  "source": "hacker_news",
  "kind": "discussion",
  "title": "Show HN: Example",
  "url": "https://news.ycombinator.com/item?id=...",
  "summary": "Short evidence text",
  "score": 123,
  "published_at": "2026-07-06T00:00:00Z",
  "launch_date": "2026-07-01",
  "product_launch_date": "2026-07-01",
  "first_seen_at": "2026-07-06",
  "evidence_published_at": "2026-07-06T00:00:00Z",
  "date_confidence": "known_launch_date",
  "signals": {
    "points": 100,
    "comments": 20
  },
  "ranking": {
    "final_score": 0.812345,
    "rrf_score": 0.018852,
    "rrf_normalized": 0.92,
    "local_relevance": 1.0,
    "freshness": 0.85,
    "engagement": 0.75,
    "source_quality": 0.82,
    "source_diversity": 0.25,
    "source_rank": 1,
    "matched_sources": ["hacker_news"],
    "launch_date_confidence": "evidence_date_only"
  },
  "raw": {}
}
```

Use `source`, `title`, `url`, `summary`, `signals`, and `ranking` when writing briefs. The script omits `raw` by default; pass `--include-raw` only when debugging adapters.

## Product Entity Entries

`products` contains grouped product entities built from `product_data` evidence:

```json
{
  "name": "Example Product",
  "canonical_key": "domain:example.com",
  "kind": "app",
  "url": "https://example.com",
  "urls": ["https://example.com"],
  "sources": ["product_hunt", "github_trending"],
  "evidence_count": 2,
  "best_ranking_score": 0.812345,
  "product_score": 0.734567,
  "product_rank": 1,
  "score_breakdown": {
    "ranking_strength": 0.812345,
    "source_coverage": 0.666667,
    "feedback_strength": 0.45,
    "evidence_depth": 0.5,
    "launch_confidence": 1.0
  },
  "rank_reasons": [
    "product evidence from product_hunt, github_trending",
    "launch date is verified inside the requested window"
  ],
  "launch_date": "2026-07-01",
  "product_launch_date": "2026-07-01",
  "first_seen_at": "2026-07-06",
  "launch_date_confidence": "known_in_range",
  "community_feedback": [],
  "feedback_summary": {},
  "feedback_count": 0,
  "feedback_sources": [],
  "evidence": []
}
```

`products` is the preferred product discovery view. `product_data` remains the source-level evidence used to build it.

`product_score` is the product-level score used to order `products`. It combines the best evidence ranking, source coverage, matched feedback strength, evidence depth, and launch-date confidence. `score_breakdown` exposes those components for downstream tuning. `rank_reasons` is a short display-ready explanation list for why the product ranked well.

`products[].community_feedback` contains feedback rows whose title, summary, URL domain, or normalized product name clearly matches the product. It is intentionally conservative; generic category pages or broad AI news pages may remain only in the top-level `community_feedback` list.

`products[].feedback_summary` and top-level `community_feedback_summary` provide a lightweight structured summary:

```json
{
  "evidence_count": 5,
  "sentiment_counts": {"positive": 1, "negative": 1, "mixed": 0, "neutral": 3},
  "praise_points": [],
  "complaint_points": [],
  "repeated_needs": [],
  "willingness_to_pay": [],
  "migration_or_alternative_signals": [],
  "top_feedback_titles": []
}
```

`product_data` and `community_feedback` are source-type partitions of ranked results:

```text
products = grouped product entities built from product_data
product_data = app, product, repository, launch platform, and directory evidence
community_feedback = community discussion, comments, videos, social feedback, and web-search/news evidence
results = backward-compatible mixed ranked list
```

Each partition is independently capped by `--limit`, while `results` remains the mixed top `--limit`.

Date fields are intentionally separate:

```text
launch_date = product/app/repository launch date when known
product_launch_date = backward-compatible alias for launch_date
first_seen_at = first date this skill saw the product in a chart/source, when known
evidence_published_at = article/post/video/chart evidence date
published_at = backward-compatible evidence publication date
date_confidence = source-level date basis such as known_launch_date, chart_date_only, trending_period_only, evidence_date_only, or unknown
```

Use `--filter-launch-date` for new-product discovery so products with known launch dates outside the requested range are removed.

Use `--product-sources` and `--feedback-sources` to route the two pipelines separately:

```bash
python scripts/just-launched.py "new AI products" --mode all --product-sources product_hunt,github_trending --feedback-sources web,hacker_news
```

`--sources` remains as a backward-compatible global override.

## Ranking

The `score` field is the raw score from a single source and is not comparable across sources. For final ordering, use `ranking.final_score`.

The ranking pipeline:

1. Sort results inside each source by raw `score`.
2. Convert each result into source-local signals: `local_relevance`, `engagement`, `freshness`, and `source_quality`.
3. Deduplicate by normalized URL, or by normalized title when no URL exists.
4. Fuse source ranks with weighted reciprocal rank fusion (`rrf_k = 60`).
5. Compute `ranking.final_score` with the formula in `ranking_model`.

`launch_date_confidence` values:

```text
known_in_range
known_out_of_range
evidence_date_only
unknown
```

`matched_sources` contains more than one source when duplicate evidence was merged.
