from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.request
from typing import Any

from ...common import (
    DEFAULT_UA,
    date_only,
    item,
)

class ProductHuntSource:
    def product_hunt(self) -> list[dict[str, Any]]:
        token = os.getenv("PRODUCT_HUNT_TOKEN")
        if not token:
            return []
        posted_after = dt.datetime.combine(self.start_date, dt.time.min, tzinfo=dt.timezone.utc).isoformat()
        topic = self._product_hunt_topic()
        query = """
        query Posts($postedAfter: DateTime, $postedBefore: DateTime, $topic: String) {
          posts(first: 20, postedAfter: $postedAfter, postedBefore: $postedBefore, topic: $topic, order: VOTES) {
            edges { node { name tagline url votesCount commentsCount createdAt } }
          }
        }
        """
        posted_before = dt.datetime.combine(self.end_date + dt.timedelta(days=1), dt.time.min, tzinfo=dt.timezone.utc).isoformat()
        payload = json.dumps({"query": query, "variables": {"postedAfter": posted_after, "postedBefore": posted_before, "topic": topic}}).encode()
        req = urllib.request.Request(
            "https://api.producthunt.com/v2/api/graphql",
            data=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": DEFAULT_UA},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("errors"):
            messages = "; ".join(str(err.get("message") or err) for err in data.get("errors", [])[:3])
            raise RuntimeError(f"Product Hunt GraphQL error: {messages}")
        rows = []
        for edge in data.get("data", {}).get("posts", {}).get("edges", []):
            n = edge.get("node", {})
            if not self._product_hunt_matches_query(n, topic):
                continue
            rows.append(item(
                "product_hunt",
                n.get("name", ""),
                n.get("url", ""),
                kind="product",
                summary=n.get("tagline", ""),
                published_at=n.get("createdAt", ""),
                product_launch_date=date_only(n.get("createdAt")),
                launch_date=date_only(n.get("createdAt")),
                evidence_published_at=n.get("createdAt", ""),
                date_confidence="known_launch_date" if n.get("createdAt") else "unknown",
                score=float(n.get("votesCount") or 0) + float(n.get("commentsCount") or 0) * 3,
                signals={
                    "votes": n.get("votesCount"),
                    "comments": n.get("commentsCount"),
                    "topic": topic or "",
                    "local_query_match": bool(self.query),
                },
                raw=n,
            ))
        return rows

    def _product_hunt_matches_query(self, product: dict[str, Any], topic: str | None) -> bool:
        terms = [
            term for term in re.findall(r"[a-z0-9]+", (self.query or "").lower())
            if term not in {
                "alternative", "alternatives", "app", "apps", "complaint", "complaints", "feedback",
                "latest", "launch", "launched", "new", "pricing", "product", "products", "recent",
                "review", "reviews", "tool", "tools",
            }
        ]
        topic_terms = {
            "artificial-intelligence": {"ai", "agent", "agents", "artificial", "intelligence", "llm"},
            "developer-tools": {"api", "code", "coding", "developer", "devtool", "github"},
            "productivity": {"calendar", "notes", "productivity", "task", "todo", "workflow"},
            "marketing": {"crm", "marketing", "sales", "seo"},
        }.get(topic or "", set())
        terms = [term for term in terms if term not in topic_terms]
        if not terms:
            return True
        haystack = f"{product.get('name') or ''} {product.get('tagline') or ''}".lower()
        return any(term in haystack for term in terms)

    def _product_hunt_topic(self) -> str | None:
        topic = os.getenv("PRODUCT_SCOUT_PRODUCT_HUNT_TOPIC", "").strip()
        if topic:
            return topic
        query = (self.query or "").lower()
        topic_keywords = [
            ("artificial-intelligence", (" ai ", "ai products", "ai tools", "artificial intelligence", "agent", "agents", "llm")),
            ("developer-tools", ("developer", "dev tool", "devtool", "api", "coding", "github", "code")),
            ("productivity", ("productivity", "workflow", "calendar", "notes", "task", "todo")),
            ("marketing", ("marketing", "seo", "sales", "crm")),
        ]
        padded = f" {query} "
        for topic_slug, keywords in topic_keywords:
            if any(keyword in padded for keyword in keywords):
                return topic_slug
        return None

