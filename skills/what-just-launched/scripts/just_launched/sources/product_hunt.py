from __future__ import annotations

import base64
import datetime as dt
import html
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from typing import Any

from ..common import (
    BROWSER_UA,
    DEFAULT_UA,
    date_only,
    date_to_epoch_end,
    date_to_epoch_start,
    get_json,
    get_text,
    item,
    post_json,
)

class ProductHuntSource:
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

