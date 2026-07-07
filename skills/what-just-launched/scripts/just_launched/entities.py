"""Product entity grouping for What Just Launched."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from .ranking import clean_text, normalize_url

MATCH_STOPWORDS = {
    "about",
    "after",
    "best",
    "chat",
    "create",
    "discover",
    "friends",
    "learn",
    "live",
    "news",
    "play",
    "sports",
    "that",
    "this",
    "with",
    "world",
}


def build_products(
    product_rows: list[dict[str, Any]],
    community_rows: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for idx, row in enumerate(product_rows):
        key = product_entity_key(row)
        if not key:
            key = f"row:{idx}"
        groups.setdefault(key, []).append(row)

    products = [build_product_entity(rows, community_rows) for rows in groups.values()]
    products.sort(
        key=lambda product: (
            product.get("best_ranking_score", 0),
            product.get("evidence_count", 0),
        ),
        reverse=True,
    )
    return products[:limit]


def product_entity_key(row: dict[str, Any]) -> str:
    url = normalize_url(str(row.get("url") or ""))
    if url:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        path = parsed.path.strip("/")
        if host in {"apps.apple.com", "play.google.com", "github.com", "producthunt.com"} and path:
            parts = path.split("/")
            return f"url:{host}/{'/'.join(parts[:3])}"
        return f"domain:{host}" if host else f"url:{url}"

    title = canonical_title(str(row.get("title") or ""))
    return f"title:{title}" if title else ""


def canonical_title(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"\b(app|apps|ai|official|beta|launch|launched|new)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:90]


def build_product_entity(rows: list[dict[str, Any]], community_rows: list[dict[str, Any]]) -> dict[str, Any]:
    best = max(rows, key=lambda row: row.get("ranking", {}).get("final_score", 0))
    sources = sorted({str(row.get("source") or "unknown") for row in rows})
    urls = []
    for row in rows:
        url = str(row.get("url") or "")
        if url and url not in urls:
            urls.append(url)

    launch_dates = sorted({str(row.get("product_launch_date") or "") for row in rows if row.get("product_launch_date")})
    confidence_rank = {"known_in_range": 3, "known_out_of_range": 2, "evidence_date_only": 1, "unknown": 0}
    launch_date_confidence = max(
        (str(row.get("ranking", {}).get("launch_date_confidence") or "unknown") for row in rows),
        key=lambda value: confidence_rank.get(value, 0),
        default="unknown",
    )

    evidence = [
        {
            "source": row.get("source"),
            "kind": row.get("kind"),
            "title": row.get("title"),
            "url": row.get("url"),
            "summary": row.get("summary"),
            "product_launch_date": row.get("product_launch_date"),
            "published_at": row.get("published_at"),
            "signals": row.get("signals", {}),
            "ranking": row.get("ranking", {}),
        }
        for row in rows
    ]
    evidence.sort(key=lambda row: row.get("ranking", {}).get("final_score", 0), reverse=True)
    feedback = match_community_feedback(best, rows, community_rows)
    feedback_sources = sorted({str(row.get("source") or "unknown") for row in feedback})

    return {
        "name": best.get("title") or "",
        "canonical_key": product_entity_key(best),
        "kind": best.get("kind") or "",
        "url": urls[0] if urls else "",
        "urls": urls,
        "sources": sources,
        "evidence_count": len(rows),
        "best_ranking_score": best.get("ranking", {}).get("final_score", 0),
        "product_launch_date": launch_dates[0] if launch_dates else "",
        "launch_date_confidence": launch_date_confidence,
        "community_feedback": feedback,
        "feedback_count": len(feedback),
        "feedback_sources": feedback_sources,
        "evidence": evidence,
    }


def match_community_feedback(
    best_product_row: dict[str, Any],
    product_rows: list[dict[str, Any]],
    community_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    product_terms = product_match_terms(best_product_row, product_rows)
    product_domains = product_match_domains(product_rows)
    matches: list[dict[str, Any]] = []
    for row in community_rows:
        score = feedback_match_score(row, product_terms, product_domains)
        if score < 0.45:
            continue
        match = {
            "source": row.get("source"),
            "kind": row.get("kind"),
            "title": row.get("title"),
            "url": row.get("url"),
            "summary": row.get("summary"),
            "published_at": row.get("published_at"),
            "signals": row.get("signals", {}),
            "ranking": row.get("ranking", {}),
            "match_score": round(score, 6),
        }
        matches.append(match)
    matches.sort(
        key=lambda row: (
            row.get("match_score", 0),
            row.get("ranking", {}).get("final_score", 0),
        ),
        reverse=True,
    )
    return matches[:5]


def product_match_terms(best_product_row: dict[str, Any], product_rows: list[dict[str, Any]]) -> set[str]:
    terms: set[str] = set()
    for row in [best_product_row, *product_rows]:
        title = str(row.get("title") or "")
        canonical = canonical_title(title)
        if canonical:
            terms.add(canonical)
        compact = canonical.replace(" ", "")
        if compact and len(compact) >= 4:
            terms.add(compact)
        for token in canonical.split():
            if len(token) >= 5 and token not in MATCH_STOPWORDS:
                terms.add(token)
    return terms


def product_match_domains(product_rows: list[dict[str, Any]]) -> set[str]:
    domains: set[str] = set()
    for row in product_rows:
        url = normalize_url(str(row.get("url") or ""))
        if not url:
            continue
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if host:
            domains.add(host)
    return domains


def feedback_match_score(
    feedback_row: dict[str, Any],
    product_terms: set[str],
    product_domains: set[str],
) -> float:
    title = canonical_title(str(feedback_row.get("title") or ""))
    summary = canonical_title(str(feedback_row.get("summary") or ""))
    combined = f"{title} {summary}".strip()
    url = normalize_url(str(feedback_row.get("url") or ""))
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    score = 0.0
    if host and host in product_domains:
        score = max(score, 1.0)
    for domain in product_domains:
        if domain and domain in url:
            score = max(score, 0.9)
    for term in product_terms:
        if not term:
            continue
        if term in title:
            score = max(score, 0.75)
        elif term in combined:
            score = max(score, 0.55)
    return score
