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

from ...common import (
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

class HackerNewsSource:
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

