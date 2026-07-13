"""Ranking and fusion logic for What Just Launched."""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import Any

import datetime as dt


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

RRF_K = 60
SOURCE_WEIGHTS = {
    "product_hunt": 1.25,
    "hacker_news": 1.15,
    "github_trending": 1.05,
    "apple_rss": 0.95,
    "itunes_search": 0.95,
    "appbrain": 0.80,
    "google_play": 0.80,
    "betalist": 0.90,
    "microlaunch": 0.92,
    "uneed": 0.82,
    "fazier": 0.92,
    "peerlist": 1.05,
    "reddit": 1.10,
    "reddit_public": 0.85,
    "lobsters": 0.82,
    "github_issues": 0.78,
    "stackexchange": 0.72,
    "xquik": 0.90,
    "x_external": 0.90,
    "youtube": 0.95,
    "brave_search": 0.88,
    "serpapi_search": 0.85,
    "tavily_search": 0.85,
    "web_search": 0.60,
}
SOURCE_QUALITY = {
    "product_hunt": 0.90,
    "hacker_news": 0.82,
    "github_trending": 0.78,
    "apple_rss": 0.74,
    "itunes_search": 0.74,
    "appbrain": 0.62,
    "google_play": 0.62,
    "betalist": 0.68,
    "microlaunch": 0.70,
    "uneed": 0.60,
    "fazier": 0.72,
    "peerlist": 0.82,
    "reddit": 0.80,
    "reddit_public": 0.62,
    "lobsters": 0.70,
    "github_issues": 0.66,
    "stackexchange": 0.62,
    "xquik": 0.68,
    "x_external": 0.68,
    "youtube": 0.70,
    "brave_search": 0.62,
    "serpapi_search": 0.58,
    "tavily_search": 0.60,
    "web_search": 0.35,
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


class RankingMixin:
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
                key={"known_in_range": 4, "inferred_in_range": 3, "known_out_of_range": 2, "evidence_date_only": 1, "unknown": 0}.get,
            )
            merged_row["_ranking"] = merged_ranking
            if len(group_rows) > 1:
                merged_row.setdefault("signals", {})
                merged_row["signals"]["matched_sources"] = sources
                merged_row["signals"]["duplicate_count"] = len(group_rows)
            merged.append(merged_row)
        return merged

    def _freshness_score(self, row: dict[str, Any]) -> float:
        date_value = row.get("launch_date") or row.get("product_launch_date") or row.get("evidence_published_at") or row.get("published_at")
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
        date_confidence = str(row.get("date_confidence") or "")
        if date_confidence in {"chart_date_only", "trending_period_only"}:
            return "evidence_date_only"
        launch_date = str(row.get("launch_date") or row.get("product_launch_date") or "")
        if date_confidence == "inferred_from_first_vote" and launch_date:
            return "inferred_in_range" if self._date_in_range(launch_date) else "known_out_of_range"
        if launch_date:
            return "known_in_range" if self._date_in_range(launch_date) else "known_out_of_range"
        if row.get("evidence_published_at") or row.get("published_at"):
            return "evidence_date_only"
        return "unknown"

