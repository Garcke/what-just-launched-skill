"""Product entity grouping for What Just Launched."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from .feedback_summary import summarize_feedback
from .ranking import clean_text, normalize_url, parse_date

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

DIRECTORY_PRODUCT_HOSTS = {
    "betalist.com",
    "fazier.com",
    "microlaunch.net",
    "uneed.best",
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

    merged_groups = merge_cross_source_groups(list(groups.values()))
    products = [build_product_entity(rows, community_rows) for rows in merged_groups]
    products.sort(
        key=lambda product: (
            product.get("product_score", 0),
            product.get("best_ranking_score", 0),
            product.get("evidence_count", 0),
        ),
        reverse=True,
    )
    for rank, product in enumerate(products, 1):
        product["product_rank"] = rank
    return products[:limit]


def merge_cross_source_groups(groups: list[list[dict[str, Any]]]) -> list[list[dict[str, Any]]]:
    merged: list[list[dict[str, Any]]] = []
    title_index: dict[str, list[int]] = {}
    for rows in groups:
        titles = {
            canonical_title(str(row.get("title") or ""))
            for row in rows
            if len(canonical_title(str(row.get("title") or ""))) >= 5
        }
        target: int | None = None
        for title in titles:
            for index in title_index.get(title, []):
                if can_merge_product_groups(merged[index], rows):
                    target = index
                    break
            if target is not None:
                break
        if target is None:
            target = len(merged)
            merged.append(list(rows))
        else:
            merged[target].extend(rows)
        for title in titles:
            if target not in title_index.setdefault(title, []):
                title_index[title].append(target)
    return merged


def can_merge_product_groups(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> bool:
    left_sources = {str(row.get("source") or "") for row in left}
    right_sources = {str(row.get("source") or "") for row in right}
    if left_sources & right_sources:
        return False
    left_dates = [parse_date(str(row.get("launch_date") or row.get("product_launch_date") or "")) for row in left]
    right_dates = [parse_date(str(row.get("launch_date") or row.get("product_launch_date") or "")) for row in right]
    known_left = [value for value in left_dates if value]
    known_right = [value for value in right_dates if value]
    if known_left and known_right:
        return min(abs((a - b).days) for a in known_left for b in known_right) <= 14
    return True


def product_entity_key(row: dict[str, Any]) -> str:
    url = normalize_url(str(row.get("url") or ""))
    if url:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        path = parsed.path.strip("/")
        if host in DIRECTORY_PRODUCT_HOSTS and path:
            parts = path.split("/")
            return f"url:{host}/{'/'.join(parts[:2])}"
        if host in {"apps.apple.com", "play.google.com", "github.com", "peerlist.io", "producthunt.com"} and path:
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

    launch_dates = sorted({str(row.get("launch_date") or row.get("product_launch_date") or "") for row in rows if row.get("launch_date") or row.get("product_launch_date")})
    first_seen_dates = sorted({str(row.get("first_seen_at") or "") for row in rows if row.get("first_seen_at")})
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
            "launch_date": row.get("launch_date"),
            "product_launch_date": row.get("product_launch_date"),
            "first_seen_at": row.get("first_seen_at"),
            "evidence_published_at": row.get("evidence_published_at"),
            "published_at": row.get("published_at"),
            "date_confidence": row.get("date_confidence"),
            "signals": row.get("signals", {}),
            "ranking": row.get("ranking", {}),
        }
        for row in rows
    ]
    evidence.sort(key=lambda row: row.get("ranking", {}).get("final_score", 0), reverse=True)
    feedback = match_community_feedback(best, rows, community_rows)
    feedback_sources = sorted({str(row.get("source") or "unknown") for row in feedback})
    score_breakdown = product_score_breakdown(best, rows, feedback, launch_date_confidence)
    product_score = round(
        0.45 * score_breakdown["ranking_strength"]
        + 0.20 * score_breakdown["source_coverage"]
        + 0.15 * score_breakdown["feedback_strength"]
        + 0.10 * score_breakdown["evidence_depth"]
        + 0.10 * score_breakdown["launch_confidence"],
        6,
    )

    return {
        "name": best.get("title") or "",
        "canonical_key": product_entity_key(best),
        "kind": best.get("kind") or "",
        "url": urls[0] if urls else "",
        "urls": urls,
        "sources": sources,
        "evidence_count": len(rows),
        "best_ranking_score": best.get("ranking", {}).get("final_score", 0),
        "product_score": product_score,
        "score_breakdown": score_breakdown,
        "rank_reasons": product_rank_reasons(rows, feedback, score_breakdown, launch_date_confidence),
        "launch_date": launch_dates[0] if launch_dates else "",
        "product_launch_date": launch_dates[0] if launch_dates else "",
        "first_seen_at": first_seen_dates[0] if first_seen_dates else "",
        "launch_date_confidence": launch_date_confidence,
        "community_feedback": feedback,
        "feedback_summary": summarize_feedback(feedback),
        "feedback_count": len(feedback),
        "feedback_sources": feedback_sources,
        "evidence": evidence,
    }


def product_score_breakdown(
    best: dict[str, Any],
    rows: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    launch_date_confidence: str,
) -> dict[str, float]:
    ranking_strength = float(best.get("ranking", {}).get("final_score") or 0.0)
    source_coverage = min(1.0, len({str(row.get("source") or "unknown") for row in rows}) / 3.0)
    evidence_depth = min(1.0, len(rows) / 4.0)
    launch_confidence_score = {
        "known_in_range": 1.0,
        "known_out_of_range": 0.35,
        "evidence_date_only": 0.65,
        "unknown": 0.20,
    }.get(launch_date_confidence, 0.20)
    if feedback:
        avg_feedback_score = sum(float(row.get("ranking", {}).get("final_score") or 0.0) for row in feedback) / len(feedback)
        feedback_strength = min(1.0, 0.45 * (len(feedback) / 5.0) + 0.55 * avg_feedback_score)
    else:
        feedback_strength = 0.0
    return {
        "ranking_strength": round(ranking_strength, 6),
        "source_coverage": round(source_coverage, 6),
        "feedback_strength": round(feedback_strength, 6),
        "evidence_depth": round(evidence_depth, 6),
        "launch_confidence": round(launch_confidence_score, 6),
    }


def product_rank_reasons(
    rows: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    score_breakdown: dict[str, float],
    launch_date_confidence: str,
) -> list[str]:
    reasons: list[str] = []
    sources = sorted({str(row.get("source") or "unknown") for row in rows})
    if sources:
        reasons.append(f"product evidence from {', '.join(sources[:4])}")
    if launch_date_confidence == "known_in_range":
        reasons.append("launch date is verified inside the requested window")
    elif launch_date_confidence == "evidence_date_only":
        reasons.append("fresh evidence exists, but launch date is not directly verified")
    if feedback:
        feedback_sources = sorted({str(row.get("source") or "unknown") for row in feedback})
        reasons.append(f"{len(feedback)} matched feedback item(s) from {', '.join(feedback_sources[:4])}")
    if score_breakdown.get("source_coverage", 0) >= 0.67:
        reasons.append("multiple independent sources support the product signal")
    if score_breakdown.get("ranking_strength", 0) >= 0.65:
        reasons.append("strong source-normalized ranking score")
    return reasons[:5]


def match_community_feedback(
    best_product_row: dict[str, Any],
    product_rows: list[dict[str, Any]],
    community_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    product_terms = product_match_terms(best_product_row, product_rows)
    product_domains = product_match_domains(product_rows)
    matches: list[dict[str, Any]] = []
    for row in community_rows:
        if str(row.get("signals", {}).get("feedback_likelihood") or "") == "low":
            continue
        score = feedback_match_score(row, product_terms, product_domains)
        if score < 0.45:
            continue
        match = {
            "source": row.get("source"),
            "kind": row.get("kind"),
            "title": row.get("title"),
            "url": row.get("url"),
            "summary": row.get("summary"),
            "evidence_published_at": row.get("evidence_published_at"),
            "published_at": row.get("published_at"),
            "date_confidence": row.get("date_confidence"),
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
