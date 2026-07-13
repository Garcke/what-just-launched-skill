"""Peerlist Launchpad product discovery adapter."""

from __future__ import annotations

import datetime as dt
import urllib.parse
from typing import Any

from ...common import BROWSER_UA, date_only, get_json, item


class PeerlistSource:
    def peerlist(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for year, week in self._peerlist_weeks():
            cursor = ""
            for _ in range(10):
                params: dict[str, Any] = {"year": year, "week": week, "limit": 20}
                if cursor:
                    params["cursor"] = cursor
                data = get_json(
                    "https://peerlist.io/api/v1/users/projects/spotlight?" + urllib.parse.urlencode(params),
                    headers={
                        "Accept": "application/json",
                        "Referer": f"https://peerlist.io/launchpad/{year}/week/{week}",
                        "User-Agent": BROWSER_UA,
                    },
                    timeout=30,
                )
                payload = data.get("data", {}) if isinstance(data, dict) else {}
                products = payload.get("spotlight", []) if isinstance(payload, dict) else []
                if not isinstance(products, list):
                    products = []
                for rank, product in enumerate(products, 1):
                    if not isinstance(product, dict):
                        continue
                    product_id = str(product.get("id") or "").strip()
                    title = str(product.get("title") or "").strip()
                    slug = str(product.get("slug") or "").strip()
                    if not product_id or not title or product_id in seen:
                        continue
                    if self.query and not self._peerlist_matches_query(product):
                        continue
                    launch_date = date_only(str(product.get("featuredOn") or payload.get("featuredOnDate") or ""))
                    if launch_date and not self._date_in_range(launch_date):
                        continue
                    seen.add(product_id)
                    upvotes = self._safe_int(product.get("upvotesCount")) or 0
                    comments = self._safe_int(product.get("commentCount")) or 0
                    bookmarks = self._safe_int(product.get("bookmarkCount")) or 0
                    peerlist_url = self._peerlist_project_url(product, slug, product_id)
                    project_url = str(product.get("projectURL") or "").strip()
                    rows.append(item(
                        "peerlist",
                        title,
                        project_url if project_url.startswith(("http://", "https://")) else peerlist_url,
                        kind="product",
                        summary=str(product.get("tagline") or "").strip(),
                        score=float(upvotes + comments * 2 + bookmarks),
                        published_at=str(product.get("featuredOn") or payload.get("featuredOnDate") or ""),
                        product_launch_date=launch_date,
                        launch_date=launch_date,
                        evidence_published_at=str(product.get("featuredOn") or payload.get("featuredOnDate") or ""),
                        date_confidence="known_launch_date" if launch_date else "unknown",
                        signals={
                            "id": product_id,
                            "slug": slug,
                            "peerlist_url": peerlist_url,
                            "logo": product.get("logo"),
                            "images": product.get("images") or [],
                            "upvotes": upvotes,
                            "comments": comments,
                            "bookmarks": bookmarks,
                            "categories": product.get("categories") or [],
                            "creator": product.get("createdBy") or {},
                            "week": week,
                            "year": year,
                            "weekly_rank": rank,
                            "launched_count": payload.get("launchedCount"),
                            "parser": "spotlight_api",
                        },
                        raw=product,
                    ))
                    if len(rows) >= self.args.limit:
                        return rows
                next_cursor = str(payload.get("cursor") or "").strip()
                if not products or not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
        return rows

    def _peerlist_weeks(self) -> list[tuple[int, int]]:
        weeks: list[tuple[int, int]] = []
        current = self.end_date
        while current >= self.start_date:
            iso = current.isocalendar()
            pair = (iso.year, iso.week)
            if pair not in weeks:
                weeks.append(pair)
            current -= dt.timedelta(days=7)
        start_iso = self.start_date.isocalendar()
        start_pair = (start_iso.year, start_iso.week)
        if start_pair not in weeks:
            weeks.append(start_pair)
        return weeks

    def _peerlist_matches_query(self, product: dict[str, Any]) -> bool:
        categories = product.get("categories") or []
        category_text = " ".join(
            str(value.get("name") or value.get("title") or value.get("slug") or "")
            if isinstance(value, dict) else str(value)
            for value in categories if value
        )
        return self._query_matches_text(" ".join((
            str(product.get("title") or ""),
            str(product.get("tagline") or ""),
            category_text,
        )))

    def _peerlist_project_url(self, product: dict[str, Any], slug: str, product_id: str) -> str:
        creator = product.get("createdBy") or {}
        if isinstance(creator, list):
            creator = creator[0] if creator else {}
        username = str(creator.get("username") or creator.get("profileHandle") or "").strip() if isinstance(creator, dict) else ""
        if username and slug:
            return f"https://peerlist.io/{urllib.parse.quote(username)}/project/{urllib.parse.quote(slug)}"
        return f"https://peerlist.io/projects/{urllib.parse.quote(slug or product_id)}"
