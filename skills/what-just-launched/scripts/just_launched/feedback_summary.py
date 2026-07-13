"""Lightweight feedback summarization for What Just Launched."""

from __future__ import annotations

import re
from typing import Any

from .ranking import clean_text

PRAISE_PATTERNS = {
    "easy_to_use": ("easy", "simple", "intuitive", "clean", "fast", "smooth"),
    "useful": ("useful", "helpful", "works well", "love", "great", "impressive"),
    "quality": ("accurate", "reliable", "polished", "stable", "powerful"),
}

COMPLAINT_PATTERNS = {
    "pricing": ("expensive", "price", "pricing", "subscription", "paywall", "cost"),
    "bugs": ("bug", "broken", "crash", "error", "issue", "does not work", "failed"),
    "performance": ("slow", "lag", "latency", "timeout", "rate limit"),
    "trust": ("privacy", "security", "tracking", "data", "spam", "scam"),
}

NEED_PATTERNS = {
    "integration": ("integrate", "integration", "api", "plugin", "extension", "workflow"),
    "automation": ("automate", "automation", "agent", "schedule", "batch"),
    "mobile": ("ios", "android", "mobile", "app"),
    "collaboration": ("team", "share", "collaborate", "workspace", "multi-user"),
}

PAYMENT_PATTERNS = {
    "willing_to_pay": ("would pay", "pay for", "worth paying", "subscribe", "paid plan"),
    "price_sensitive": ("too expensive", "not worth", "free alternative", "cheaper", "cancel"),
}

MIGRATION_PATTERNS = {
    "switching": ("switch from", "migrate", "replace", "alternative to", "instead of"),
    "comparison": ("vs ", "versus", "better than", "worse than", "competitor"),
}


def summarize_feedback(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        row for row in rows
        if str(row.get("signals", {}).get("feedback_likelihood") or "") != "low"
    ]
    evidence_count = len(rows)
    return {
        "evidence_count": evidence_count,
        "sentiment_counts": sentiment_counts(rows),
        "praise_points": matched_topics(rows, PRAISE_PATTERNS),
        "complaint_points": matched_topics(rows, COMPLAINT_PATTERNS),
        "repeated_needs": matched_topics(rows, NEED_PATTERNS),
        "willingness_to_pay": matched_topics(rows, PAYMENT_PATTERNS),
        "migration_or_alternative_signals": matched_topics(rows, MIGRATION_PATTERNS),
        "top_feedback_titles": [str(row.get("title") or "") for row in rows[:5] if row.get("title")],
    }


def sentiment_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"positive": 0, "negative": 0, "mixed": 0, "neutral": 0}
    for row in rows:
        text = row_text(row)
        positive = any(keyword in text for keywords in PRAISE_PATTERNS.values() for keyword in keywords)
        negative = any(keyword in text for keywords in COMPLAINT_PATTERNS.values() for keyword in keywords)
        if positive and negative:
            counts["mixed"] += 1
        elif positive:
            counts["positive"] += 1
        elif negative:
            counts["negative"] += 1
        else:
            counts["neutral"] += 1
    return counts


def matched_topics(rows: list[dict[str, Any]], patterns: dict[str, tuple[str, ...]]) -> list[dict[str, Any]]:
    topics: list[dict[str, Any]] = []
    for topic, keywords in patterns.items():
        evidence = []
        for row in rows:
            text = row_text(row)
            hits = [keyword for keyword in keywords if keyword in text]
            if not hits:
                continue
            evidence.append({
                "title": row.get("title") or "",
                "url": row.get("url") or "",
                "keywords": sorted(set(hits))[:5],
            })
        if evidence:
            topics.append({"topic": topic, "count": len(evidence), "evidence": evidence[:3]})
    topics.sort(key=lambda item: item["count"], reverse=True)
    return topics


def row_text(row: dict[str, Any]) -> str:
    text = f"{row.get('title') or ''} {row.get('summary') or ''}"
    return re.sub(r"\s+", " ", clean_text(text))
