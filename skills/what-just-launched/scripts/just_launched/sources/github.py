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

class GitHubSources:
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

