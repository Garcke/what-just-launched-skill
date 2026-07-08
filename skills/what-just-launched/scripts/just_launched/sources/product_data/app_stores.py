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
    now_utc,
    post_json,
)

class AppStoreSources:
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
        detail_limit = max(0, int(getattr(self.args, "appark_detail_limit", 10) or 0))
        detail_count = 0
        for chart, apps in (data.get("data") or {}).items():
            if not isinstance(apps, list):
                continue
            for rank, app in enumerate(apps, 1):
                detail = {}
                app_id = str(app.get("app_id") or "")
                if app_id and detail_count < detail_limit:
                    detail = self._appark_app_detail(app_id)
                    if detail:
                        detail_count += 1
                title = app.get("app_name") or app.get("name") or app.get("title") or app.get("trackName") or ""
                title = detail.get("app_name") or title
                url = detail.get("app_url") or app.get("app_url") or app.get("url") or ""
                release_date = date_only(detail.get("release_date")) if detail.get("release_date") else ""
                summary = detail.get("subtitle") or app.get("subtitle") or detail.get("description") or app.get("description") or ""
                signals = {
                    "chart": chart,
                    "rank": rank,
                    "category": self.args.category,
                    "date_basis": "known_release_date" if release_date else "chart_date",
                    "app_id": app_id,
                    "rank_change": app.get("rank_change"),
                    "rank_days": app.get("rank_days"),
                    "developer_name": detail.get("developer_name") or app.get("developer_name"),
                    "rating": detail.get("rating"),
                    "reviews": detail.get("reviews"),
                    "version": detail.get("version"),
                    "categories": detail.get("categories"),
                    "has_detail": bool(detail),
                }
                rows.append(item(
                    "appark",
                    title,
                    url,
                    kind="app",
                    summary=summary[:500],
                    score=max(1, 100 - rank),
                    product_launch_date=release_date,
                    launch_date=release_date,
                    first_seen_at=self.today,
                    evidence_published_at=release_date or self.today,
                    date_confidence="known_launch_date" if release_date else "chart_date_only",
                    signals=signals,
                    raw={"chart": app, "detail": detail} if detail else app,
                ))
        return rows

    def _appark_app_detail(self, app_id: str) -> dict[str, Any]:
        params = urllib.parse.urlencode({
            "app_id": app_id,
            "platform": "1",
            "country": self.market,
        })
        try:
            data = get_json(
                f"https://appark.ai/api/app/app-detail?{params}",
                headers={"User-Agent": BROWSER_UA, "Accept": "application/json"},
                timeout=25,
            )
        except Exception:
            return {}
        payload = data.get("data") if isinstance(data, dict) else None
        return payload if isinstance(payload, dict) else {}

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
                    launch_date=launch_date,
                    evidence_published_at=launch_date,
                    date_confidence="known_launch_date" if launch_date else "unknown",
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
                    launch_date=launch_date,
                    evidence_published_at=app.get("currentVersionReleaseDate") or launch_date,
                    date_confidence="known_launch_date" if launch_date else "evidence_date_only" if app.get("currentVersionReleaseDate") else "unknown",
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
            rows.append(item("appbrain", title, f"https://www.appbrain.com{href}", kind="app", score=10, date_confidence="unknown", signals={"query": self.query}))
        return rows[: self.args.limit]

