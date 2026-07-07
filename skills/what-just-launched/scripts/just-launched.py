#!/usr/bin/env python3
"""What Just Launched search engine.

Runs lightweight product discovery and feedback searches across free or
user-configured sources, then emits normalized JSON for an agent to synthesize.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


CONFIG_DIR = Path(os.getenv("PRODUCT_SCOUT_CONFIG_DIR", os.getenv("WHAT_JUST_LAUNCHED_CONFIG_DIR", "~/.config/what-just-launched"))).expanduser()
CONFIG_FILE = CONFIG_DIR / ".env"
LEGACY_CONFIG_FILE = Path("~/.config/product-scout/.env").expanduser()
DEFAULT_UA = os.getenv(
    "PRODUCT_SCOUT_USER_AGENT",
    "windows:product-scout:0.1.0 (by /u/configure-product-scout)",
)
BROWSER_UA = os.getenv(
    "PRODUCT_SCOUT_BROWSER_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
)
RRF_K = 60
SOURCE_WEIGHTS = {
    "product_hunt": 1.25,
    "appark": 0.95,
    "hacker_news": 1.15,
    "github_trending": 1.05,
    "github_search": 1.05,
    "apple_rss": 0.95,
    "itunes_search": 0.95,
    "appbrain": 0.80,
    "google_play": 0.80,
    "betalist": 0.90,
    "ai_directory": 0.80,
    "reddit": 1.10,
    "reddit_public": 0.85,
    "xquik": 0.90,
    "x_external": 0.90,
    "youtube": 0.95,
    "brave_search": 0.85,
    "exa_search": 0.85,
    "serper_search": 0.85,
    "tavily_search": 0.85,
    "duckduckgo": 0.70,
    "web_search": 0.60,
}
SOURCE_QUALITY = {
    "product_hunt": 0.90,
    "appark": 0.72,
    "hacker_news": 0.82,
    "github_trending": 0.78,
    "github_search": 0.80,
    "apple_rss": 0.74,
    "itunes_search": 0.74,
    "appbrain": 0.62,
    "google_play": 0.62,
    "betalist": 0.68,
    "ai_directory": 0.62,
    "reddit": 0.80,
    "reddit_public": 0.62,
    "xquik": 0.68,
    "x_external": 0.68,
    "youtube": 0.70,
    "brave_search": 0.58,
    "exa_search": 0.60,
    "serper_search": 0.58,
    "tavily_search": 0.60,
    "duckduckgo": 0.45,
    "web_search": 0.35,
}


def load_env_file(path: Path = CONFIG_FILE) -> dict[str, str]:
    loaded: dict[str, str] = {}
    if path == CONFIG_FILE and not path.exists() and LEGACY_CONFIG_FILE.exists():
        path = LEGACY_CONFIG_FILE
    if not path.exists():
        return loaded
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


def env_file_keys(path: Path = CONFIG_FILE) -> list[str]:
    if path == CONFIG_FILE and not path.exists() and LEGACY_CONFIG_FILE.exists():
        path = LEGACY_CONFIG_FILE
    if not path.exists():
        return []
    keys: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.append(line.split("=", 1)[0].strip())
    return sorted(k for k in keys if k)


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:3] + "*" * (len(value) - 6) + value[-3:]


def append_config(entries: dict[str, str], path: Path = CONFIG_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    existing_keys = set()
    for line in existing.splitlines():
        if "=" in line and not line.strip().startswith("#"):
            existing_keys.add(line.split("=", 1)[0].strip())
    with path.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        for key, value in entries.items():
            if key in existing_keys:
                continue
            f.write(f"{key}={value}\n")


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_days_ago(days: int) -> str:
    return (now_utc() - dt.timedelta(days=days)).date().isoformat()


def epoch_days_ago(days: int) -> int:
    return int((now_utc() - dt.timedelta(days=days)).timestamp())


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(text).date()
    except ValueError:
        pass
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def date_only(value: str | None) -> str:
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else ""


def date_to_epoch_start(value: dt.date) -> int:
    return int(dt.datetime.combine(value, dt.time.min, tzinfo=dt.timezone.utc).timestamp())


def date_to_epoch_end(value: dt.date) -> int:
    return int(dt.datetime.combine(value, dt.time.max, tzinfo=dt.timezone.utc).timestamp())


def get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, timeout: int = 25) -> Any:
    body = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    req_headers.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def get_text(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return raw.decode("utf-8", "replace")


def status(name: str, state: str, reason: str = "") -> dict[str, str]:
    return {"source": name, "status": state, "reason": reason}


def item(
    source: str,
    title: str,
    url: str,
    *,
    kind: str,
    summary: str = "",
    score: float = 0,
    published_at: str = "",
    product_launch_date: str = "",
    signals: dict[str, Any] | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "kind": kind,
        "title": title,
        "url": url,
        "summary": summary,
        "score": score,
        "published_at": published_at,
        "product_launch_date": product_launch_date,
        "signals": signals or {},
        "raw": raw or {},
    }


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip().lower()


def normalize_url(value: str) -> str:
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    keep = []
    for key, val in query:
        lk = key.lower()
        if lk.startswith("utm_") or lk in {"ref", "ref_src", "fbclid", "gclid", "igshid"}:
            continue
        keep.append((key, val))
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunparse((scheme, netloc, path, "", urllib.parse.urlencode(keep), ""))


def dedupe_key(row: dict[str, Any]) -> str:
    url = normalize_url(str(row.get("url") or ""))
    if url:
        return f"url:{url}"
    title = re.sub(r"[^a-z0-9]+", " ", clean_text(str(row.get("title") or ""))).strip()
    return f"title:{title[:90]}"


class ProductScout:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.market = args.market.lower()
        self.end_date = parse_date(args.until) or now_utc().date()
        self.start_date = parse_date(args.since) or (self.end_date - dt.timedelta(days=max(1, int(args.days)) - 1))
        if self.start_date > self.end_date:
            raise ValueError("--since cannot be after --until")
        self.days = max(1, (self.end_date - self.start_date).days + 1)
        self.query = args.query.strip()
        self.today = now_utc().date().isoformat()

    def preflight(self) -> list[dict[str, str]]:
        checks = [
            status("product_hunt", "available" if os.getenv("PRODUCT_HUNT_TOKEN") else "missing_config", "set PRODUCT_HUNT_TOKEN for Product Hunt GraphQL"),
            status("appark", "available", "uses public top-charts endpoint with browser User-Agent"),
            status("hacker_news", "available", "uses free HN Algolia API"),
            status("github_trending", "available", "scrapes public GitHub Trending page"),
            status("apple_rss_itunes", "available", "uses Apple RSS and iTunes Search APIs"),
            status("google_play_appbrain", "available", "uses AppBrain page search as a lightweight Android discovery fallback"),
            status("betalist", "available", "scrapes public BetaList pages at low request volume"),
            status("ai_directory", "available", "scrapes public AI directory pages at low request volume"),
            status("reddit", "available" if self._has_reddit_oauth() else "missing_config", "use REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT; public fallback is disabled by default"),
            status("x_twitter", "available" if self._has_x_config() else "missing_config", "set XQUIK_API_KEY, XAI_API_KEY, PRODUCT_SCOUT_X_ADAPTER_COMMAND, FROM_BROWSER=auto, or AUTH_TOKEN+CT0"),
            status("youtube", "available" if os.getenv("YOUTUBE_API_KEY") else "missing_config", "set YOUTUBE_API_KEY; yt-dlp is optional for transcripts"),
            status("web_search", "available", "uses PRODUCT_SCOUT_WEB_PROVIDERS; supports Brave, Exa, DuckDuckGo, Serper, Tavily"),
        ]
        return checks

    def diagnose(self) -> dict[str, Any]:
        return {
            "config_file": str(CONFIG_FILE),
            "config_file_exists": CONFIG_FILE.exists(),
            "legacy_config_file": str(LEGACY_CONFIG_FILE),
            "legacy_config_file_exists": LEGACY_CONFIG_FILE.exists(),
            "config_file_keys": env_file_keys(),
            "credentials": {
                "PRODUCT_HUNT_TOKEN": bool(os.getenv("PRODUCT_HUNT_TOKEN")),
                "REDDIT_CLIENT_ID": bool(os.getenv("REDDIT_CLIENT_ID")),
                "REDDIT_CLIENT_SECRET": bool(os.getenv("REDDIT_CLIENT_SECRET")),
                "REDDIT_USER_AGENT": bool(os.getenv("REDDIT_USER_AGENT")),
                "XQUIK_API_KEY": bool(os.getenv("XQUIK_API_KEY")),
                "XAI_API_KEY": bool(os.getenv("XAI_API_KEY")),
                "PRODUCT_SCOUT_X_ADAPTER_COMMAND": bool(os.getenv("PRODUCT_SCOUT_X_ADAPTER_COMMAND")),
                "AUTH_TOKEN": bool(os.getenv("AUTH_TOKEN")),
                "CT0": bool(os.getenv("CT0")),
                "YOUTUBE_API_KEY": bool(os.getenv("YOUTUBE_API_KEY")),
                "BRAVE_API_KEY": bool(os.getenv("BRAVE_API_KEY")),
                "EXA_API_KEY": bool(os.getenv("EXA_API_KEY")),
                "SERPER_API_KEY": bool(os.getenv("SERPER_API_KEY")),
                "TAVILY_API_KEY": bool(os.getenv("TAVILY_API_KEY")),
                "PRODUCT_SCOUT_WEB_PROVIDERS": os.getenv("PRODUCT_SCOUT_WEB_PROVIDERS", "brave,exa,serper,tavily,duckduckgo"),
            },
            "commands": {
                "yt-dlp": self._command_exists("yt-dlp"),
                "gh": self._command_exists("gh"),
            },
            "preflight": self.preflight(),
        }

    def run(self) -> dict[str, Any]:
        selected = self._selected_sources()
        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        runners = {
            "product_hunt": self.product_hunt,
            "appark": self.appark,
            "hacker_news": self.hacker_news,
            "github_trending": self.github_trending,
            "apple": self.apple,
            "google_play": self.google_play,
            "betalist": self.betalist,
            "ai_directory": self.ai_directory,
            "reddit": self.reddit,
            "x": self.x_twitter,
            "youtube": self.youtube,
            "web": self.web_search,
        }
        for source in selected:
            fn = runners.get(source)
            if not fn:
                errors.append(status(source, "unknown_source", "not registered"))
                continue
            try:
                results.extend(fn())
            except urllib.error.HTTPError as exc:
                errors.append(status(source, f"http_{exc.code}", exc.reason or "HTTP error"))
            except Exception as exc:  # Keep one bad source from killing the whole search.
                errors.append(status(source, "error", f"{type(exc).__name__}: {exc}"))
        if self.args.filter_launch_date:
            results = [
                row
                for row in results
                if not row.get("product_launch_date") or self._date_in_range(str(row.get("product_launch_date") or ""))
            ]
        if not self.args.include_raw:
            for row in results:
                row.pop("raw", None)
        ranked_results = self._rank_results(results)
        return {
            "query": self.query,
            "mode": self.args.mode,
            "market": self.market,
            "days": self.days,
            "time_range": {"since": self.start_date.isoformat(), "until": self.end_date.isoformat()},
            "generated_at": now_utc().isoformat(),
            "preflight": self.preflight(),
            "errors": errors,
            "ranking_model": {
                "name": "source-normalized-weighted-rrf",
                "rrf_k": RRF_K,
                "formula": "0.35*rrf + 0.25*local_relevance + 0.15*freshness + 0.10*source_quality + 0.10*engagement + 0.05*source_diversity",
            },
            "results": ranked_results[: self.args.limit],
        }

    def _rank_results(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        annotated = self._annotate_source_ranks(rows)
        merged = self._merge_duplicates(annotated)
        max_rrf = max((row["_ranking"]["rrf_score"] for row in merged), default=0.0) or 1.0
        for row in merged:
            ranking = row["_ranking"]
            rrf_norm = ranking["rrf_score"] / max_rrf
            final_score = (
                0.35 * rrf_norm
                + 0.25 * ranking["local_relevance"]
                + 0.15 * ranking["freshness"]
                + 0.10 * ranking["source_quality"]
                + 0.10 * ranking["engagement"]
                + 0.05 * ranking["source_diversity"]
            )
            ranking["rrf_normalized"] = round(rrf_norm, 6)
            ranking["final_score"] = round(final_score, 6)
            row["ranking"] = {
                "final_score": ranking["final_score"],
                "rrf_score": round(ranking["rrf_score"], 6),
                "rrf_normalized": ranking["rrf_normalized"],
                "local_relevance": round(ranking["local_relevance"], 6),
                "freshness": round(ranking["freshness"], 6),
                "engagement": round(ranking["engagement"], 6),
                "source_quality": round(ranking["source_quality"], 6),
                "source_diversity": round(ranking["source_diversity"], 6),
                "source_rank": ranking["source_rank"],
                "matched_sources": ranking["matched_sources"],
                "launch_date_confidence": ranking["launch_date_confidence"],
            }
            row.pop("_ranking", None)
        return sorted(
            merged,
            key=lambda row: (
                row.get("ranking", {}).get("final_score", 0),
                row.get("ranking", {}).get("freshness", 0),
                row.get("score", 0),
            ),
            reverse=True,
        )

    def _annotate_source_ranks(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_source: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_source.setdefault(str(row.get("source") or "unknown"), []).append(row)

        annotated: list[dict[str, Any]] = []
        for source, source_rows in by_source.items():
            sorted_rows = sorted(source_rows, key=lambda row: float(row.get("score") or 0), reverse=True)
            scores = [float(row.get("score") or 0) for row in sorted_rows]
            score_min = min(scores, default=0.0)
            score_max = max(scores, default=0.0)
            denom = score_max - score_min
            total = max(1, len(sorted_rows))
            for rank, row in enumerate(sorted_rows, 1):
                raw_score = float(row.get("score") or 0)
                engagement = 1.0 if total == 1 and raw_score > 0 else (raw_score - score_min) / denom if denom else 0.0
                local_relevance = 1.0 if total == 1 else 1.0 - ((rank - 1) / max(1, total - 1))
                row = dict(row)
                row["_ranking"] = {
                    "source_rank": rank,
                    "local_relevance": clamp(local_relevance),
                    "engagement": clamp(engagement),
                    "freshness": self._freshness_score(row),
                    "source_quality": SOURCE_QUALITY.get(source, 0.50),
                    "source_weight": SOURCE_WEIGHTS.get(source, 0.75),
                    "rrf_score": SOURCE_WEIGHTS.get(source, 0.75) / (RRF_K + rank),
                    "matched_sources": [source],
                    "source_diversity": 0.0,
                    "launch_date_confidence": self._launch_date_confidence(row),
                }
                annotated.append(row)
        return annotated

    def _merge_duplicates(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for idx, row in enumerate(rows):
            key = dedupe_key(row)
            if key == "title:":
                key = f"row:{idx}"
            groups.setdefault(key, []).append(row)

        merged: list[dict[str, Any]] = []
        for group_rows in groups.values():
            winner = max(
                group_rows,
                key=lambda row: (
                    row["_ranking"]["source_quality"],
                    row["_ranking"]["local_relevance"],
                    row["_ranking"]["engagement"],
                ),
            )
            merged_row = dict(winner)
            merged_ranking = dict(winner["_ranking"])
            sources = sorted({str(row.get("source") or "unknown") for row in group_rows})
            merged_ranking["matched_sources"] = sources
            merged_ranking["rrf_score"] = sum(row["_ranking"]["rrf_score"] for row in group_rows)
            merged_ranking["local_relevance"] = max(row["_ranking"]["local_relevance"] for row in group_rows)
            merged_ranking["freshness"] = max(row["_ranking"]["freshness"] for row in group_rows)
            merged_ranking["engagement"] = max(row["_ranking"]["engagement"] for row in group_rows)
            merged_ranking["source_quality"] = max(row["_ranking"]["source_quality"] for row in group_rows)
            merged_ranking["source_rank"] = min(row["_ranking"]["source_rank"] for row in group_rows)
            merged_ranking["source_diversity"] = clamp((len(sources) - 1) / 4.0)
            merged_ranking["launch_date_confidence"] = max(
                (row["_ranking"]["launch_date_confidence"] for row in group_rows),
                key={"known_in_range": 3, "known_out_of_range": 2, "evidence_date_only": 1, "unknown": 0}.get,
            )
            merged_row["_ranking"] = merged_ranking
            if len(group_rows) > 1:
                merged_row.setdefault("signals", {})
                merged_row["signals"]["matched_sources"] = sources
                merged_row["signals"]["duplicate_count"] = len(group_rows)
            merged.append(merged_row)
        return merged

    def _freshness_score(self, row: dict[str, Any]) -> float:
        date_value = row.get("product_launch_date") or row.get("published_at")
        parsed = parse_date(str(date_value or ""))
        if not parsed:
            return 0.35
        if parsed < self.start_date:
            age_days = (self.start_date - parsed).days
            return clamp(0.35 - min(age_days, 30) / 100.0)
        if parsed > self.end_date:
            return 0.20
        span = max(1, (self.end_date - self.start_date).days)
        age_days = (self.end_date - parsed).days
        return clamp(1.0 - (age_days / (span + 1)) * 0.55)

    def _launch_date_confidence(self, row: dict[str, Any]) -> str:
        launch_date = str(row.get("product_launch_date") or "")
        if launch_date:
            return "known_in_range" if self._date_in_range(launch_date) else "known_out_of_range"
        if row.get("published_at"):
            return "evidence_date_only"
        return "unknown"

    def product_hunt(self) -> list[dict[str, Any]]:
        token = os.getenv("PRODUCT_HUNT_TOKEN")
        if not token:
            return []
        posted_after = (now_utc() - dt.timedelta(days=self.days)).isoformat()
        posted_after = dt.datetime.combine(self.start_date, dt.time.min, tzinfo=dt.timezone.utc).isoformat()
        query = """
        query Posts($postedAfter: DateTime, $postedBefore: DateTime, $search: String) {
          posts(first: 20, postedAfter: $postedAfter, postedBefore: $postedBefore, order: VOTES, search: $search) {
            edges { node { name tagline url votesCount commentsCount createdAt } }
          }
        }
        """
        posted_before = dt.datetime.combine(self.end_date + dt.timedelta(days=1), dt.time.min, tzinfo=dt.timezone.utc).isoformat()
        payload = json.dumps({"query": query, "variables": {"postedAfter": posted_after, "postedBefore": posted_before, "search": self.query or None}}).encode()
        req = urllib.request.Request(
            "https://api.producthunt.com/v2/api/graphql",
            data=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": DEFAULT_UA},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        rows = []
        for edge in data.get("data", {}).get("posts", {}).get("edges", []):
            n = edge.get("node", {})
            rows.append(item(
                "product_hunt",
                n.get("name", ""),
                n.get("url", ""),
                kind="product",
                summary=n.get("tagline", ""),
                published_at=n.get("createdAt", ""),
                product_launch_date=date_only(n.get("createdAt")),
                score=float(n.get("votesCount") or 0) + float(n.get("commentsCount") or 0) * 3,
                signals={"votes": n.get("votesCount"), "comments": n.get("commentsCount")},
                raw=n,
            ))
        return rows

    def appark(self) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode({
            "category": self.args.category,
            "platform": "1",
            "country": self.market,
            "date": self.today,
            "date_utc": now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "time_zone": self.args.time_zone,
            "page": 1,
            "page_size": min(self.args.limit, 50),
        })
        data = get_json(
            f"https://appark.ai/api/charts/top-charts?{params}",
            headers={"User-Agent": BROWSER_UA, "Accept": "application/json"},
        )
        rows = []
        for chart, apps in (data.get("data") or {}).items():
            if not isinstance(apps, list):
                continue
            for rank, app in enumerate(apps, 1):
                title = app.get("app_name") or app.get("name") or app.get("title") or app.get("trackName") or ""
                url = app.get("app_url") or app.get("url") or ""
                rows.append(item(
                    "appark",
                    title,
                    url,
                    kind="app",
                    summary=app.get("subtitle") or app.get("description") or "",
                    score=max(1, 100 - rank),
                    signals={"chart": chart, "rank": rank, "category": self.args.category},
                    raw=app,
                ))
        return rows

    def hacker_news(self) -> list[dict[str, Any]]:
        if not self.query:
            query = "launch OR launched OR Show HN"
        else:
            query = self.query
        params = urllib.parse.urlencode({
            "query": query,
            "tags": "story,comment" if self.args.mode != "discovery" else "story",
            "numericFilters": f"created_at_i>{date_to_epoch_start(self.start_date)},created_at_i<{date_to_epoch_end(self.end_date)}",
            "hitsPerPage": min(self.args.limit, 50),
        })
        data = get_json(f"https://hn.algolia.com/api/v1/search_by_date?{params}", headers={"User-Agent": DEFAULT_UA})
        rows = []
        for hit in data.get("hits", []):
            title = hit.get("title") or hit.get("story_title") or hit.get("comment_text", "")[:80]
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            points = hit.get("points") or 0
            comments = hit.get("num_comments") or 0
            summary_text = hit.get("comment_text") or hit.get("story_text") or ""
            rows.append(item(
                "hacker_news",
                html.unescape(re.sub("<[^>]+>", "", title or "")),
                url,
                kind="discussion" if hit.get("comment_text") else "post",
                summary=html.unescape(re.sub("<[^>]+>", "", summary_text))[:500],
                published_at=hit.get("created_at", ""),
                score=float(points) + float(comments) * 2,
                signals={"points": points, "comments": comments, "author": hit.get("author")},
                raw=hit,
            ))
        return rows

    def github_trending(self) -> list[dict[str, Any]]:
        if self.query:
            return self.github_repo_search()
        since = "daily" if self.days <= 2 else "weekly" if self.days <= 14 else "monthly"
        url = f"https://github.com/trending?since={since}"
        text = get_text(url, headers={"User-Agent": BROWSER_UA})
        rows = []
        for block in re.findall(r"<article[^>]*>(.*?)</article>", text, flags=re.S):
            m = re.search(r'<h2[^>]*>.*?<a href="([^"]+)".*?</a>', block, flags=re.S)
            if not m:
                continue
            repo_path = html.unescape(m.group(1)).strip()
            title = repo_path.strip("/").replace("\n", "").replace(" ", "")
            desc_m = re.search(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', block, flags=re.S)
            stars_m = re.search(r'(\d[\d,]*) stars today|(\d[\d,]*) stars this week|(\d[\d,]*) stars this month', block)
            stars = next((int(x.replace(",", "")) for x in (stars_m.groups() if stars_m else []) if x), 0)
            desc = html.unescape(re.sub("<[^>]+>", "", desc_m.group(1))).strip() if desc_m else ""
            rows.append(item(
                "github_trending",
                title,
                f"https://github.com{repo_path}",
                kind="repository",
                summary=desc,
                score=float(stars),
                signals={"stars_period": stars, "since": since},
            ))
        return rows

    def github_repo_search(self) -> list[dict[str, Any]]:
        q = f"{self.query} created:{self.start_date.isoformat()}..{self.end_date.isoformat()}"
        params = urllib.parse.urlencode({"q": q, "sort": "stars", "order": "desc", "per_page": min(self.args.limit, 30)})
        data = get_json(f"https://api.github.com/search/repositories?{params}", headers={"User-Agent": DEFAULT_UA, "Accept": "application/vnd.github+json"})
        rows = []
        for repo in data.get("items", []):
            rows.append(item(
                "github_search",
                repo.get("full_name", ""),
                repo.get("html_url", ""),
                kind="repository",
                summary=repo.get("description") or "",
                published_at=repo.get("created_at", ""),
                product_launch_date=date_only(repo.get("created_at")),
                score=float(repo.get("stargazers_count") or 0),
                signals={
                    "stars": repo.get("stargazers_count"),
                    "forks": repo.get("forks_count"),
                    "language": repo.get("language"),
                    "created_at": repo.get("created_at"),
                },
                raw=repo,
            ))
        return rows

    def apple(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rss_url = f"https://rss.marketingtools.apple.com/api/v2/{self.market}/apps/top-free/{min(self.args.limit, 50)}/apps.json"
        try:
            data = get_json(rss_url, headers={"User-Agent": DEFAULT_UA})
            for rank, app in enumerate(data.get("feed", {}).get("results", []), 1):
                launch_date = app.get("releaseDate") or ""
                if self.args.filter_launch_date and launch_date and not self._date_in_range(launch_date):
                    continue
                rows.append(item(
                    "apple_rss",
                    app.get("name", ""),
                    app.get("url", ""),
                    kind="app",
                    summary=app.get("artistName", ""),
                    product_launch_date=launch_date,
                    score=max(1, 100 - rank),
                    signals={"rank": rank, "genre": app.get("genres", [{}])[0].get("name") if app.get("genres") else None},
                    raw=app,
                ))
        except Exception:
            pass
        if self.query:
            params = urllib.parse.urlencode({"term": self.query, "country": self.market, "entity": "software", "limit": min(self.args.limit, 50)})
            data = get_json(f"https://itunes.apple.com/search?{params}", headers={"User-Agent": DEFAULT_UA})
            for app in data.get("results", []):
                launch_date = app.get("releaseDate") or ""
                if self.args.filter_launch_date and launch_date and not self._date_in_range(launch_date):
                    continue
                rows.append(item(
                    "itunes_search",
                    app.get("trackName", ""),
                    app.get("trackViewUrl", ""),
                    kind="app",
                    summary=app.get("description", "")[:500],
                    product_launch_date=launch_date,
                    score=float(app.get("userRatingCount") or 0),
                    signals={"rating": app.get("averageUserRating"), "rating_count": app.get("userRatingCount"), "genre": app.get("primaryGenreName"), "current_version_release_date": app.get("currentVersionReleaseDate")},
                    raw=app,
                ))
        return rows

    def google_play(self) -> list[dict[str, Any]]:
        if not self.query:
            return []
        q = urllib.parse.quote_plus(self.query)
        url = f"https://www.appbrain.com/search?q={q}"
        text = get_text(url, headers={"User-Agent": BROWSER_UA})
        rows = []
        for m in re.finditer(r'<a href="(/app/[^"]+)".*?>(.*?)</a>', text, flags=re.S):
            href = html.unescape(m.group(1))
            title = html.unescape(re.sub("<[^>]+>", "", m.group(2))).strip()
            if not title:
                continue
            rows.append(item("appbrain", title, f"https://www.appbrain.com{href}", kind="app", score=10, signals={"query": self.query}))
        return rows[: self.args.limit]

    def betalist(self) -> list[dict[str, Any]]:
        url = "https://betalist.com/"
        if self.query:
            url = f"https://betalist.com/search?q={urllib.parse.quote_plus(self.query)}"
        text = get_text(url, headers={"User-Agent": BROWSER_UA})
        rows = []
        for m in re.finditer(r'<a[^>]+href="(/startups/[^"]+)"[^>]*>(.*?)</a>', text, flags=re.S):
            title = html.unescape(re.sub("<[^>]+>", "", m.group(2))).strip()
            if title and len(title) < 120:
                rows.append(item("betalist", title, f"https://betalist.com{m.group(1)}", kind="startup", score=20))
        return rows[: self.args.limit]

    def ai_directory(self) -> list[dict[str, Any]]:
        url = "https://theresanaiforthat.com/"
        if self.query:
            url = f"https://theresanaiforthat.com/s/{urllib.parse.quote_plus(self.query)}/"
        text = get_text(url, headers={"User-Agent": BROWSER_UA})
        rows = []
        for m in re.finditer(r'<a[^>]+href="(/ai/[^"]+)"[^>]*>(.*?)</a>', text, flags=re.S):
            title = html.unescape(re.sub("<[^>]+>", "", m.group(2))).strip()
            if title and len(title) < 120:
                rows.append(item("ai_directory", title, f"https://theresanaiforthat.com{m.group(1)}", kind="ai_tool", score=15))
        return rows[: self.args.limit]

    def reddit(self) -> list[dict[str, Any]]:
        if not self._has_reddit_oauth():
            if os.getenv("PRODUCT_SCOUT_ALLOW_REDDIT_PUBLIC_JSON", "").lower() == "true":
                return self._reddit_public_low_rate()
            return []
        token = self._reddit_token()
        params = urllib.parse.urlencode({"q": self.query, "sort": "relevance", "t": "month", "limit": min(self.args.limit, 25), "type": "link"})
        data = get_json(
            f"https://oauth.reddit.com/search?{params}",
            headers={"Authorization": f"Bearer {token}", "User-Agent": os.getenv("REDDIT_USER_AGENT", DEFAULT_UA)},
        )
        rows = []
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            row = item(
                "reddit",
                d.get("title", ""),
                "https://www.reddit.com" + d.get("permalink", ""),
                kind="discussion",
                summary=d.get("selftext", "")[:500],
                published_at=dt.datetime.fromtimestamp(d.get("created_utc", 0), dt.timezone.utc).isoformat() if d.get("created_utc") else "",
                score=float(d.get("score") or 0) + float(d.get("num_comments") or 0) * 2,
                signals={"subreddit": d.get("subreddit"), "upvotes": d.get("score"), "comments": d.get("num_comments")},
                raw=d,
            )
            row["id"] = d.get("id")
            row["permalink"] = d.get("permalink")
            rows.append(row)
        if os.getenv("PRODUCT_SCOUT_REDDIT_COMMENTS", "true").lower() == "true":
            for row in sorted(rows, key=lambda r: r.get("score", 0), reverse=True)[:3]:
                self._attach_reddit_comments(row, token)
        return rows

    def x_twitter(self) -> list[dict[str, Any]]:
        if os.getenv("XQUIK_API_KEY"):
            return self._xquik_search()
        if os.getenv("PRODUCT_SCOUT_X_ADAPTER_COMMAND"):
            return self._external_x_adapter()
        if os.getenv("XAI_API_KEY"):
            return [item(
                "x_twitter",
                "XAI_API_KEY configured; adapter not enabled",
                "https://x.com/search",
                kind="adapter_notice",
                summary="xAI key is present, but this engine does not guess xAI's X-search contract. Set PRODUCT_SCOUT_X_ADAPTER_COMMAND or XQUIK_API_KEY for executable X search.",
                signals={"configured": "XAI_API_KEY"},
            )]
        if os.getenv("FROM_BROWSER") == "auto" or (os.getenv("AUTH_TOKEN") and os.getenv("CT0")):
            return [item(
                "x_twitter",
                "Browser-cookie X mode configured; adapter not enabled",
                "https://x.com/search",
                kind="adapter_notice",
                summary="Browser-cookie auth is present, but this conservative engine does not scrape x.com HTML. Set PRODUCT_SCOUT_X_ADAPTER_COMMAND to a consented local adapter such as Bird.",
                signals={"configured": "browser_or_manual_cookie"},
            )]
        return []

    def youtube(self) -> list[dict[str, Any]]:
        key = os.getenv("YOUTUBE_API_KEY")
        if not key or not self.query:
            return []
        published_after = dt.datetime.combine(self.start_date, dt.time.min, tzinfo=dt.timezone.utc).isoformat().replace("+00:00", "Z")
        published_before = dt.datetime.combine(self.end_date + dt.timedelta(days=1), dt.time.min, tzinfo=dt.timezone.utc).isoformat().replace("+00:00", "Z")
        params = urllib.parse.urlencode({
            "part": "snippet",
            "q": self.query,
            "type": "video",
            "order": "relevance",
            "publishedAfter": published_after,
            "publishedBefore": published_before,
            "maxResults": min(self.args.limit, 25),
            "key": key,
        })
        data = get_json(f"https://www.googleapis.com/youtube/v3/search?{params}", headers={"User-Agent": DEFAULT_UA})
        rows = []
        video_ids = []
        for video in data.get("items", []):
            vid = video.get("id", {}).get("videoId")
            if vid:
                video_ids.append(vid)
            snip = video.get("snippet", {})
            rows.append(item(
                "youtube",
                snip.get("title", ""),
                f"https://www.youtube.com/watch?v={vid}",
                kind="video",
                summary=snip.get("description", ""),
                published_at=snip.get("publishedAt", ""),
                score=25,
                signals={"channel": snip.get("channelTitle")},
                raw=video,
            ))
        stats = self._youtube_video_stats(video_ids, key)
        for row in rows:
            vid = row["url"].split("v=")[-1] if "v=" in row["url"] else ""
            if vid in stats:
                row["signals"].update(stats[vid])
                row["score"] = float(stats[vid].get("view_count") or 0) / 1000 + float(stats[vid].get("comment_count") or 0) * 2 + float(stats[vid].get("like_count") or 0) / 100
        if os.getenv("PRODUCT_SCOUT_YOUTUBE_COMMENTS", "false").lower() == "true":
            for row in sorted(rows, key=lambda r: r.get("score", 0), reverse=True)[:3]:
                self._attach_youtube_comments(row, key)
        return rows

    def web_search(self) -> list[dict[str, Any]]:
        providers = [
            p.strip().lower()
            for p in os.getenv("PRODUCT_SCOUT_WEB_PROVIDERS", "brave,exa,serper,tavily,duckduckgo").split(",")
            if p.strip()
        ]
        errors: list[str] = []
        for provider in providers:
            try:
                if provider == "brave" and os.getenv("BRAVE_API_KEY"):
                    rows = self._brave_search()
                elif provider == "exa" and os.getenv("EXA_API_KEY"):
                    rows = self._exa_search()
                elif provider == "serper" and os.getenv("SERPER_API_KEY"):
                    rows = self._serper_search()
                elif provider == "tavily" and os.getenv("TAVILY_API_KEY"):
                    rows = self._tavily_search()
                elif provider in ("duckduckgo", "ddg"):
                    rows = self._duckduckgo_search()
                else:
                    continue
                if rows:
                    return rows
            except Exception as exc:
                errors.append(f"{provider}: {type(exc).__name__}: {exc}")
                continue
        if errors:
            return [item(
                "web_search",
                "All configured web providers failed",
                "",
                kind="source_error",
                summary="; ".join(errors)[:500],
                signals={"providers": providers},
            )]
        return []

    def _selected_sources(self) -> list[str]:
        if self.args.sources == "all":
            if self.args.mode == "discovery":
                return ["product_hunt", "appark", "hacker_news", "github_trending", "apple", "google_play", "betalist", "ai_directory"]
            if self.args.mode == "feedback":
                return ["reddit", "x", "youtube", "hacker_news", "web"]
            return ["product_hunt", "appark", "hacker_news", "github_trending", "apple", "google_play", "betalist", "ai_directory", "reddit", "x", "youtube", "web"]
        return [s.strip() for s in self.args.sources.split(",") if s.strip()]

    def _has_reddit_oauth(self) -> bool:
        return bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET"))

    def _reddit_token(self) -> str:
        client_id = os.environ["REDDIT_CLIENT_ID"]
        secret = os.environ["REDDIT_CLIENT_SECRET"]
        basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
        data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
        req = urllib.request.Request(
            "https://www.reddit.com/api/v1/access_token",
            data=data,
            headers={"Authorization": f"Basic {basic}", "User-Agent": os.getenv("REDDIT_USER_AGENT", DEFAULT_UA)},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["access_token"]

    def _reddit_public_low_rate(self) -> list[dict[str, Any]]:
        if not self.query:
            return []
        time.sleep(1.5)
        params = urllib.parse.urlencode({"q": self.query, "sort": "relevance", "t": "month", "limit": min(self.args.limit, 10)})
        data = get_json(f"https://www.reddit.com/search.json?{params}", headers={"User-Agent": os.getenv("REDDIT_USER_AGENT", DEFAULT_UA)})
        rows = []
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            rows.append(item("reddit_public", d.get("title", ""), "https://www.reddit.com" + d.get("permalink", ""), kind="discussion", score=float(d.get("score") or 0), signals={"comments": d.get("num_comments")}))
        return rows

    def _attach_reddit_comments(self, row: dict[str, Any], token: str) -> None:
        permalink = row.get("permalink")
        if not permalink:
            return
        url = f"https://oauth.reddit.com{permalink}.json?limit=5&sort=top"
        try:
            data = get_json(
                url,
                headers={"Authorization": f"Bearer {token}", "User-Agent": os.getenv("REDDIT_USER_AGENT", DEFAULT_UA)},
                timeout=20,
            )
        except Exception:
            return
        comments = []
        if isinstance(data, list) and len(data) > 1:
            for child in data[1].get("data", {}).get("children", [])[:5]:
                d = child.get("data", {})
                body = d.get("body")
                if body:
                    comments.append({"body": body[:500], "score": d.get("score"), "author": d.get("author")})
        if comments:
            row["signals"]["top_comments"] = comments

    def _has_x_config(self) -> bool:
        return bool(
            os.getenv("XAI_API_KEY")
            or os.getenv("XQUIK_API_KEY")
            or os.getenv("PRODUCT_SCOUT_X_ADAPTER_COMMAND")
            or os.getenv("FROM_BROWSER") == "auto"
            or (os.getenv("AUTH_TOKEN") and os.getenv("CT0"))
        )

    def _youtube_video_stats(self, video_ids: list[str], key: str) -> dict[str, dict[str, Any]]:
        if not video_ids:
            return {}
        params = urllib.parse.urlencode({"part": "statistics", "id": ",".join(video_ids[:50]), "key": key})
        try:
            data = get_json(f"https://www.googleapis.com/youtube/v3/videos?{params}", headers={"User-Agent": DEFAULT_UA})
        except Exception:
            return {}
        out: dict[str, dict[str, Any]] = {}
        for video in data.get("items", []):
            stats = video.get("statistics", {})
            out[video.get("id", "")] = {
                "view_count": self._safe_int(stats.get("viewCount")),
                "like_count": self._safe_int(stats.get("likeCount")),
                "comment_count": self._safe_int(stats.get("commentCount")),
            }
        return out

    def _attach_youtube_comments(self, row: dict[str, Any], key: str) -> None:
        if "v=" not in row.get("url", ""):
            return
        video_id = row["url"].split("v=")[-1]
        params = urllib.parse.urlencode({
            "part": "snippet",
            "videoId": video_id,
            "order": "relevance",
            "maxResults": 5,
            "textFormat": "plainText",
            "key": key,
        })
        try:
            data = get_json(f"https://www.googleapis.com/youtube/v3/commentThreads?{params}", headers={"User-Agent": DEFAULT_UA})
        except Exception:
            return
        comments = []
        for thread in data.get("items", []):
            snip = thread.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            text = snip.get("textDisplay")
            if text:
                comments.append({"text": text[:500], "likes": snip.get("likeCount"), "author": snip.get("authorDisplayName")})
        if comments:
            row["signals"]["top_comments"] = comments

    def _xquik_search(self) -> list[dict[str, Any]]:
        if not self.query:
            return []
        since = self.start_date.isoformat()
        until = (self.end_date + dt.timedelta(days=1)).isoformat()
        q = f"{self.query} since:{since} until:{until}"
        params = urllib.parse.urlencode({"q": q, "queryType": "Top", "limit": min(self.args.limit, 40)})
        data = get_json(
            f"https://xquik.com/api/v1/x/tweets/search?{params}",
            headers={"X-Api-Key": os.environ["XQUIK_API_KEY"], "User-Agent": DEFAULT_UA},
            timeout=30,
        )
        rows = []
        for idx, tweet in enumerate(data.get("tweets", []) if isinstance(data, dict) else []):
            author = tweet.get("author") or {}
            username = str(author.get("username") or "").lstrip("@")
            tweet_id = str(tweet.get("id") or "")
            url = f"https://x.com/{username}/status/{tweet_id}" if username and tweet_id else "https://x.com/search"
            text = str(tweet.get("text") or "").strip()
            likes = self._safe_int(tweet.get("likeCount"))
            reposts = self._safe_int(tweet.get("retweetCount"))
            replies = self._safe_int(tweet.get("replyCount"))
            quotes = self._safe_int(tweet.get("quoteCount"))
            views = self._safe_int(tweet.get("viewCount"))
            bookmarks = self._safe_int(tweet.get("bookmarkCount"))
            score_value = (likes or 0) + (reposts or 0) * 2 + (replies or 0) * 2 + (quotes or 0) * 2 + (bookmarks or 0) * 3
            rows.append(item(
                "xquik",
                text[:90] or f"Tweet {idx + 1}",
                url,
                kind="social_post",
                summary=text[:500],
                published_at=str(tweet.get("createdAt") or ""),
                score=float(score_value),
                signals={
                    "author": username,
                    "likes": likes,
                    "reposts": reposts,
                    "replies": replies,
                    "quotes": quotes,
                    "views": views,
                    "bookmarks": bookmarks,
                },
                raw=tweet,
            ))
        return rows

    def _external_x_adapter(self) -> list[dict[str, Any]]:
        command = os.environ["PRODUCT_SCOUT_X_ADAPTER_COMMAND"]
        payload = {
            "query": self.query,
            "days": self.days,
            "from_date": self.start_date.isoformat(),
            "to_date": self.end_date.isoformat(),
            "limit": self.args.limit,
        }
        completed = subprocess.run(
            command,
            input=json.dumps(payload),
            text=True,
            shell=True,
            capture_output=True,
            timeout=60,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"external X adapter failed: {completed.stderr.strip()[:300]}")
        data = json.loads(completed.stdout)
        raw_items = data.get("items", data if isinstance(data, list) else [])
        rows = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("text") or raw.get("summary") or raw.get("title") or "")
            rows.append(item(
                "x_external",
                str(raw.get("title") or text[:90] or "X result"),
                str(raw.get("url") or "https://x.com/search"),
                kind="social_post",
                summary=text[:500],
                published_at=str(raw.get("date") or raw.get("published_at") or ""),
                score=float(raw.get("score") or 0),
                signals=raw.get("signals") or raw.get("engagement") or {},
                raw=raw,
            ))
        return rows

    def _brave_search(self) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode({"q": self.query, "count": min(self.args.limit, 20), "freshness": f"pd{self.days}"})
        data = get_json(
            f"https://api.search.brave.com/res/v1/web/search?{params}",
            headers={"X-Subscription-Token": os.environ["BRAVE_API_KEY"], "Accept": "application/json", "User-Agent": DEFAULT_UA},
        )
        rows = []
        for r in data.get("web", {}).get("results", []):
            rows.append(item("brave_search", r.get("title", ""), r.get("url", ""), kind="web_result", summary=r.get("description", ""), score=10, raw=r))
        return rows

    def _exa_search(self) -> list[dict[str, Any]]:
        payload = json.dumps({"query": self.query, "numResults": min(self.args.limit, 20), "startPublishedDate": self.start_date.isoformat(), "endPublishedDate": self.end_date.isoformat()}).encode()
        req = urllib.request.Request(
            "https://api.exa.ai/search",
            data=payload,
            headers={"x-api-key": os.environ["EXA_API_KEY"], "Content-Type": "application/json", "User-Agent": DEFAULT_UA},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        rows = []
        for r in data.get("results", []):
            rows.append(item("exa_search", r.get("title", ""), r.get("url", ""), kind="web_result", summary=r.get("text", "")[:500], score=10, raw=r))
        return rows

    def _serper_search(self) -> list[dict[str, Any]]:
        data = post_json(
            "https://google.serper.dev/search",
            {"q": self.query, "num": min(self.args.limit, 20)},
            headers={"X-API-KEY": os.environ["SERPER_API_KEY"], "User-Agent": DEFAULT_UA},
        )
        rows = []
        for r in data.get("organic", []):
            rows.append(item(
                "serper_search",
                r.get("title", ""),
                r.get("link", ""),
                kind="web_result",
                summary=r.get("snippet", ""),
                score=10,
                signals={"position": r.get("position")},
                raw=r,
            ))
        return rows

    def _tavily_search(self) -> list[dict[str, Any]]:
        data = post_json(
            "https://api.tavily.com/search",
            {
                "api_key": os.environ["TAVILY_API_KEY"],
                "query": self.query,
                "max_results": min(self.args.limit, 20),
                "search_depth": "basic",
                "days": self.days,
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
            },
            headers={"User-Agent": DEFAULT_UA},
        )
        rows = []
        for r in data.get("results", []):
            rows.append(item(
                "tavily_search",
                r.get("title", ""),
                r.get("url", ""),
                kind="web_result",
                summary=r.get("content", ""),
                score=float(r.get("score") or 10),
                raw=r,
            ))
        return rows

    def _duckduckgo_search(self) -> list[dict[str, Any]]:
        if not self.query:
            return []
        time.sleep(float(os.getenv("PRODUCT_SCOUT_DDG_DELAY", "1.0")))
        params = urllib.parse.urlencode({"q": self.query, "kl": self._ddg_region(), "df": self._ddg_time_filter()})
        text = get_text(
            f"https://html.duckduckgo.com/html/?{params}",
            headers={
                "User-Agent": BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=25,
        )
        rows = []
        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'(?:<a[^>]+class="result__snippet"[^>]*>|<div[^>]+class="result__snippet"[^>]*>)(.*?)</(?:a|div)>',
            flags=re.S,
        )
        for idx, m in enumerate(pattern.finditer(text), 1):
            href = html.unescape(m.group(1))
            title = html.unescape(re.sub("<[^>]+>", "", m.group(2))).strip()
            snippet = html.unescape(re.sub("<[^>]+>", "", m.group(3))).strip()
            url = self._normalize_ddg_url(href)
            rows.append(item(
                "duckduckgo",
                title,
                url,
                kind="web_result",
                summary=snippet,
                score=max(1, 30 - idx),
                signals={"position": idx, "region": self._ddg_region(), "time_filter": self._ddg_time_filter()},
            ))
            if len(rows) >= min(self.args.limit, 20):
                break
        return rows

    def _normalize_ddg_url(self, href: str) -> str:
        if href.startswith("//duckduckgo.com/l/?"):
            query = urllib.parse.parse_qs(urllib.parse.urlparse("https:" + href).query)
            if query.get("uddg"):
                return query["uddg"][0]
        if href.startswith("/l/?"):
            query = urllib.parse.parse_qs(urllib.parse.urlparse("https://duckduckgo.com" + href).query)
            if query.get("uddg"):
                return query["uddg"][0]
        return href

    def _ddg_region(self) -> str:
        mapping = {
            "us": "us-en",
            "cn": "cn-zh",
            "jp": "jp-jp",
            "kr": "kr-kr",
            "gb": "uk-en",
            "uk": "uk-en",
            "de": "de-de",
            "fr": "fr-fr",
        }
        return os.getenv("PRODUCT_SCOUT_DDG_REGION", mapping.get(self.market, "wt-wt"))

    def _ddg_time_filter(self) -> str:
        if self.days <= 1:
            return "d"
        if self.days <= 7:
            return "w"
        if self.days <= 31:
            return "m"
        return "y"

    def _date_in_range(self, value: str) -> bool:
        parsed = parse_date(value)
        if not parsed:
            return False
        return self.start_date <= parsed <= self.end_date

    def _safe_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _command_exists(self, command: str) -> bool:
        exe = "where.exe" if os.name == "nt" else "which"
        try:
            completed = subprocess.run([exe, command], capture_output=True, text=True, timeout=5)
            return completed.returncode == 0
        except Exception:
            return False


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    parser = argparse.ArgumentParser(prog="just-launched", description="Find recently launched products and early launch signals.")
    parser.add_argument("query", nargs="?", default="", help="Product, category, competitor, or market query.")
    parser.add_argument("--mode", choices=["discovery", "feedback", "all"], default="all")
    parser.add_argument("--sources", default="all", help="Comma-separated source ids or all.")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--since", default="", help="Start date in YYYY-MM-DD. Overrides --days start.")
    parser.add_argument("--until", default="", help="End date in YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--market", default="us")
    parser.add_argument("--category", default="36", help="AppPark category id; 36 means all categories.")
    parser.add_argument("--time-zone", default="Asia/Shanghai")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--filter-launch-date", action="store_true", help="Keep products only when product_launch_date is inside the time range. Best for new-product discovery.")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--write-config", action="append", default=[], metavar="KEY=VALUE", help="Append a missing key to ~/.config/what-just-launched/.env.")
    parser.add_argument("--include-raw", action="store_true", help="Include raw source payloads for debugging.")
    args = parser.parse_args(argv)

    if args.write_config:
        entries: dict[str, str] = {}
        for pair in args.write_config:
            if "=" not in pair:
                raise SystemExit(f"--write-config expects KEY=VALUE, got: {pair}")
            key, value = pair.split("=", 1)
            entries[key.strip()] = value.strip()
        append_config(entries)
        print(json.dumps({"config_file": str(CONFIG_FILE), "written_keys": sorted(entries.keys())}, ensure_ascii=False, indent=2))
        return 0

    scout = ProductScout(args)
    data = scout.diagnose() if args.diagnose else scout.preflight() if args.preflight else scout.run()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
