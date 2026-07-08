from __future__ import annotations

import datetime as dt
import html
import re
import urllib.parse
from typing import Any

from ...common import (
    BROWSER_UA,
    DEFAULT_UA,
    date_only,
    get_json,
    get_text,
    item,
)

class AppStoreSources:
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

