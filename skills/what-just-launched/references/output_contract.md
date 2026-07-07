# What Just Launched Output Contract

The script emits UTF-8 JSON.

## Top-Level Object

```json
{
  "query": "AI video editor",
  "mode": "all",
  "market": "us",
  "days": 30,
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
    "formula": "0.35*rrf + 0.25*local_relevance + 0.15*freshness + 0.10*source_quality + 0.10*engagement + 0.05*source_diversity"
  },
  "product_data": [],
  "community_feedback": [],
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
  "product_launch_date": "2026-07-01",
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

`product_data` and `community_feedback` are source-type partitions of ranked results:

```text
product_data = app, product, repository, launch platform, and directory evidence
community_feedback = community discussion, comments, videos, and web feedback evidence
results = backward-compatible mixed ranked list
```

Each partition is independently capped by `--limit`, while `results` remains the mixed top `--limit`.

`published_at` and `product_launch_date` are intentionally separate:

```text
published_at = evidence/article/post/video date
product_launch_date = product/app/repository/launch date when known
```

Use `--filter-launch-date` for new-product discovery so products with known launch dates outside the requested range are removed.

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
