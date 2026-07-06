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
  "raw": {}
}
```

Use `source`, `title`, `url`, `summary`, and `signals` when writing briefs. The script omits `raw` by default; pass `--include-raw` only when debugging adapters.

`published_at` and `product_launch_date` are intentionally separate:

```text
published_at = evidence/article/post/video date
product_launch_date = product/app/repository/launch date when known
```

Use `--filter-launch-date` for new-product discovery so products with known launch dates outside the requested range are removed.
