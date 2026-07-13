from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ...common import (
    BROWSER_UA,
    DEFAULT_UA,
    date_only,
    get_firecrawl_page_text,
    get_json,
    get_page_text,
    get_text,
    item,
)

class DirectorySources:
    def betalist(self) -> list[dict[str, Any]]:
        rows = self._betalist_feed_rows()
        if rows and not self.query:
            return rows[: self.args.limit]
        url = "https://betalist.com/"
        if self.query:
            url = f"https://betalist.com/search?q={urllib.parse.quote_plus(self.query)}"
        text, parser = get_page_text(url, env_flag="PRODUCT_SCOUT_BETALIST_USE_FIRECRAWL")
        page_rows = self._betalist_rows(text, parser)
        if not page_rows and parser == "html":
            fallback = get_firecrawl_page_text(url, env_flag="PRODUCT_SCOUT_BETALIST_USE_FIRECRAWL")
            if fallback:
                text, parser = fallback
                page_rows = self._betalist_rows(text, parser)
        if self.query:
            query_rows = self._filter_betalist_feed_rows(rows)
            merged = query_rows + [row for row in page_rows if row.get("url") not in {item.get("url") for item in query_rows}]
            return merged[: self.args.limit]
        return (rows or page_rows)[: self.args.limit]

    def _betalist_feed_rows(self) -> list[dict[str, Any]]:
        try:
            text = get_text(
                "https://feeds.feedburner.com/BetaList",
                headers={"Accept": "application/atom+xml,application/xml,text/xml,*/*", "User-Agent": DEFAULT_UA},
                timeout=30,
            )
        except Exception:
            return []
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        rows: list[dict[str, Any]] = []
        for idx, entry in enumerate(root.findall("atom:entry", ns), 1):
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()
            updated = (entry.findtext("atom:updated", default="", namespaces=ns) or "").strip()
            entry_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
            link = entry_id
            link_node = entry.find("atom:link[@rel='alternate']", ns)
            if link_node is not None:
                link = str(link_node.attrib.get("href") or link)
            clean_link = self._clean_betalist_url(link)
            slug = clean_link.rstrip("/").split("/")[-1]
            content = entry.findtext("atom:content", default="", namespaces=ns) or ""
            content_html = html.unescape(content)
            summary = self._html_text(content_html)
            image_match = re.search(r"<img[^>]+src=['\"]([^'\"]+)['\"]", content_html, flags=re.I)
            if not title or not clean_link:
                continue
            rows.append(item(
                "betalist",
                title,
                clean_link,
                kind="startup",
                summary=summary,
                score=float(max(1, 50 - idx)),
                published_at=published,
                product_launch_date=date_only(published),
                launch_date=date_only(published),
                evidence_published_at=published or updated,
                date_confidence="known_launch_date" if published else "evidence_date_only" if updated else "unknown",
                signals={
                    "slug": slug,
                    "feed_id": entry_id,
                    "updated": updated,
                    "image": image_match.group(1) if image_match else "",
                    "parser": "atom_feed",
                },
            ))
            if len(rows) >= max(self.args.limit, 20):
                break
        return rows

    def _filter_betalist_feed_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.query:
            return rows
        return [row for row in rows if self._query_matches_text(f"{row.get('title', '')} {row.get('summary', '')}")]

    def _clean_betalist_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse((parsed.scheme or "https", parsed.netloc or "betalist.com", parsed.path.rstrip("/") or "/", "", "", ""))

    def _html_text(self, value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", value)
        text = html.unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    def _betalist_rows(self, text: str, parser: str) -> list[dict[str, Any]]:
        rows = []
        seen: set[str] = set()
        for idx, m in enumerate(re.finditer(r'href="(/startups/[^"]+)"', text), 1):
            href = m.group(1)
            slug = href.rstrip("/").split("/")[-1]
            if not slug or slug in seen:
                continue
            window = text[m.end(): m.end() + 2500]
            spans = [
                html.unescape(re.sub("<[^>]+>", " ", span)).strip()
                for span in re.findall(r"<span[^>]*>(.*?)</span>", window, flags=re.S)
            ]
            spans = [re.sub(r"\s+", " ", span).strip() for span in spans if span.strip()]
            title = spans[0] if spans else slug.replace("-", " ").title()
            summary = spans[1] if len(spans) > 1 else ""
            if not title or len(title) > 120:
                continue
            seen.add(slug)
            rows.append(item(
                "betalist",
                title,
                f"https://betalist.com{href}",
                kind="startup",
                summary=summary,
                score=float(max(1, 40 - len(rows))),
                evidence_published_at=self.today,
                date_confidence="evidence_date_only",
                signals={"slug": slug, "parser": parser, "date_basis": "page_evidence"},
            ))
            if len(rows) >= self.args.limit:
                break
        return rows

    def microlaunch(self) -> list[dict[str, Any]]:
        url = "https://microlaunch.net/"
        text, parser = get_page_text(url, env_flag="PRODUCT_SCOUT_MICROLAUNCH_USE_FIRECRAWL")
        products = self._microlaunch_products(text)
        if not products and parser == "html":
            fallback = get_firecrawl_page_text(url, env_flag="PRODUCT_SCOUT_MICROLAUNCH_USE_FIRECRAWL")
            if fallback:
                text, parser = fallback
                products = self._microlaunch_products(text)
        launches_by_product_id = self._microlaunch_launches_by_product_id()
        rows = []
        for idx, product in enumerate(products, 1):
            title = str(product.get("codename") or "").strip()
            slug = str(product.get("slug") or "").strip()
            launch = launches_by_product_id.get(str(product.get("id") or ""))
            created_at = str((launch or {}).get("created_at") or product.get("created_at") or "").strip()
            launch_date = str((launch or {}).get("start_date") or date_only(created_at)).strip()
            summary = str(product.get("problem_label") or product.get("solution_label") or (launch or {}).get("description") or "").strip()
            if not title or not slug:
                continue
            if self.query and not self._microlaunch_matches_query(product):
                continue
            score = self._safe_float((launch or {}).get("product_points_week"))
            if score is None:
                score = self._safe_float((launch or {}).get("score_week"))
            if score is None:
                score = self._safe_float((launch or {}).get("votes"))
            if score is None:
                score = float(max(1, 40 - idx))
            feedback = (launch or {}).get("feedback_arr") or []
            rows.append(item(
                "microlaunch",
                title,
                f"https://microlaunch.net/p/{urllib.parse.quote(slug)}",
                kind="product",
                summary=summary,
                score=float(score),
                published_at=created_at,
                product_launch_date=date_only(launch_date),
                launch_date=date_only(launch_date),
                evidence_published_at=created_at,
                date_confidence="known_launch_date" if launch_date else "unknown",
                signals={
                    "id": product.get("id"),
                    "slug": slug,
                    "launch_id": (launch or {}).get("id"),
                    "batch": (launch or {}).get("batch_num"),
                    "website_url": (launch or {}).get("url"),
                    "votes": (launch or {}).get("votes"),
                    "votes_week": (launch or {}).get("votes_week"),
                    "score_week": (launch or {}).get("score_week"),
                    "product_points_week": (launch or {}).get("product_points_week"),
                    "feedback_count": len(feedback) if isinstance(feedback, list) else 0,
                    "market": product.get("market", ""),
                    "product_type": product.get("product_type", ""),
                    "offer_type": product.get("offer_type", ""),
                    "stage": product.get("stage", ""),
                    "is_premium": product.get("is_premium", False),
                    "parser": "page_plus_launches_api" if launch else parser,
                },
                raw={**product, "launch": launch or {}},
            ))
            if len(rows) >= self.args.limit:
                break
        return rows

    def _microlaunch_launches_by_product_id(self) -> dict[str, dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for batch in self._microlaunch_batches():
            query = urllib.parse.urlencode({"channel": "MicroLaunch", "batch": batch})
            url = f"https://nextjs-twitter-api.vercel.app/api/launches?{query}"
            try:
                data = get_json(
                    url,
                    headers={
                        "Accept": "application/json",
                        "Origin": "https://microlaunch.net",
                        "Referer": "https://microlaunch.net/",
                        "User-Agent": DEFAULT_UA,
                    },
                    timeout=30,
                )
            except Exception:
                continue
            launches = data.get("data", {}).get("launches", []) if isinstance(data, dict) else []
            for launch in launches if isinstance(launches, list) else []:
                product_id = str(launch.get("product_id") or "")
                if not product_id:
                    continue
                previous = rows.get(product_id)
                if previous and str(previous.get("created_at") or "") >= str(launch.get("created_at") or ""):
                    continue
                rows[product_id] = launch
        return rows

    def _microlaunch_batches(self) -> list[int]:
        batches: list[int] = []
        current = dt.date(self.start_date.year, self.start_date.month, 1)
        end = dt.date(self.end_date.year, self.end_date.month, 1)
        while current <= end:
            batches.append(current.year * 100 + current.month)
            if current.month == 12:
                current = dt.date(current.year + 1, 1, 1)
            else:
                current = dt.date(current.year, current.month + 1, 1)
        return batches

    def _microlaunch_products(self, text: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        pattern = r'\{\\"created_at\\":\\"[^\\"]+\\",\\"id\\":\d+.*?\\"is_premium\\":(?:true|false)\}'
        for match in re.finditer(pattern, text, flags=re.S):
            raw = match.group(0).replace('\\"', '"')
            try:
                product = json.loads(raw)
            except json.JSONDecodeError:
                continue
            slug = str(product.get("slug") or "")
            if not slug or slug in seen:
                continue
            seen.add(slug)
            rows.append(product)
        return sorted(rows, key=lambda row: str(row.get("created_at") or ""), reverse=True)

    def _microlaunch_matches_query(self, product: dict[str, Any]) -> bool:
        query_terms = [
            term
            for term in re.findall(r"[a-z0-9]+", self.query.lower())
            if (len(term) > 2 or term == "ai") and term not in {"new", "product", "products", "tool", "tools", "app", "apps"}
        ]
        if not query_terms:
            return True
        haystack = " ".join(
            str(product.get(key) or "")
            for key in ("codename", "problem_label", "solution_label", "market", "product_type", "offer_type", "stage")
        ).lower()
        return any(re.search(r"\bai\b", haystack) if term == "ai" else term in haystack for term in query_terms)

    def fazier(self) -> list[dict[str, Any]]:
        products = self._fazier_api_products()
        parser = "next_data_json" if products else ""
        url = "https://fazier.com/"
        if not products:
            text, parser = get_page_text(url, env_flag="PRODUCT_SCOUT_FAZIER_USE_FIRECRAWL")
            products = self._fazier_products(text)
        if not products and parser == "html":
            fallback = get_firecrawl_page_text(url, env_flag="PRODUCT_SCOUT_FAZIER_USE_FIRECRAWL")
            if fallback:
                text, parser = fallback
                products = self._fazier_products(text)
        rows = []
        for idx, product in enumerate(products, 1):
            title = str(product.get("name") or "").strip()
            slug = str(product.get("slug") or "").strip()
            launch_date = str(product.get("launch_date") or "").strip()
            if not title or not slug:
                continue
            if self.query and not self._directory_matches_query(product, ("name", "tagline", "category_type", "pricing_type")):
                continue
            rows.append(item(
                "fazier",
                title,
                f"https://fazier.com/launches/{urllib.parse.quote(slug)}",
                kind="product",
                summary=str(product.get("tagline") or ""),
                score=float(product.get("upvotes_count") or max(1, 40 - idx)),
                published_at=launch_date,
                product_launch_date=date_only(launch_date),
                launch_date=date_only(launch_date),
                evidence_published_at=launch_date,
                date_confidence="known_launch_date" if launch_date else "unknown",
                signals={
                    "id": product.get("id"),
                    "slug": slug,
                    "upvotes": product.get("upvotes_count"),
                    "comments": product.get("comments_count"),
                    "pricing_type": product.get("pricing_type", ""),
                    "category_type": product.get("category_type", ""),
                    "created_at": product.get("created_at", ""),
                    "parser": parser,
                },
                raw=product,
            ))
            if len(rows) >= self.args.limit:
                break
        return rows

    def _fazier_api_products(self) -> list[dict[str, Any]]:
        try:
            text = get_text("https://fazier.com/", headers={"User-Agent": BROWSER_UA}, timeout=30)
        except Exception:
            return []
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', text, flags=re.S)
        if not match:
            return []
        try:
            data = json.loads(html.unescape(match.group(1)))
        except json.JSONDecodeError:
            return []
        build_id = str(data.get("buildId") or "").strip()
        if not build_id:
            return []
        url = f"https://fazier.com/_next/data/{urllib.parse.quote(build_id)}/index.json"
        try:
            data = get_json(url, headers={"Accept": "application/json", "User-Agent": DEFAULT_UA}, timeout=30)
        except Exception:
            return []
        return self._fazier_products_from_groups(data.get("pageProps", {}).get("posts", []))

    def _fazier_products(self, text: str) -> list[dict[str, Any]]:
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', text, flags=re.S)
        if not match:
            return []
        try:
            data = json.loads(html.unescape(match.group(1)))
        except json.JSONDecodeError:
            return []
        groups = data.get("props", {}).get("pageProps", {}).get("posts", [])
        return self._fazier_products_from_groups(groups)

    def _fazier_products_from_groups(self, groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for group in groups:
            for product in group.get("posts", []) if isinstance(group, dict) else []:
                slug = str(product.get("slug") or "")
                if slug and slug not in seen:
                    seen.add(slug)
                    rows.append(product)
        return sorted(rows, key=lambda row: str(row.get("launch_date") or row.get("created_at") or ""), reverse=True)

    def uneed(self) -> list[dict[str, Any]]:
        rows = self._uneed_api_rows()
        if rows:
            return rows[: self.args.limit]
        url = "https://www.uneed.best/"
        text, parser = get_page_text(url, env_flag="PRODUCT_SCOUT_UNEED_USE_FIRECRAWL")
        rows = self._uneed_rows(text, parser)
        if not rows and parser == "html":
            fallback = get_firecrawl_page_text(url, env_flag="PRODUCT_SCOUT_UNEED_USE_FIRECRAWL")
            if fallback:
                text, parser = fallback
                rows = self._uneed_rows(text, parser)
        return rows[: self.args.limit]

    def _uneed_api_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        today = dt.date.fromisoformat(self.today)
        effective_end = min(self.end_date, today)
        if self.start_date > effective_end:
            return rows

        daily_dates: set[dt.date] = set()
        week_start = effective_end - dt.timedelta(days=effective_end.weekday())
        first_week = self.start_date - dt.timedelta(days=self.start_date.weekday())
        weeks: list[dt.date] = []
        while week_start >= first_week:
            weeks.append(week_start)
            week_start -= dt.timedelta(days=7)

        for week_start in weeks:
            week_end = week_start + dt.timedelta(days=6)
            range_start = max(self.start_date, week_start)
            range_end = min(effective_end, week_end)
            if week_end < today:
                self._uneed_add_weekly_rows(rows, seen, week_start, range_start, range_end)
            else:
                self._uneed_add_daily_range(rows, seen, range_start, range_end, daily_dates)
            if len(rows) >= self.args.limit:
                return rows[: self.args.limit]

        # Weekly archives contain winners, not every daily launch. Fill sparse or
        # query-specific results from daily ladders only when the archive is insufficient.
        for week_start in weeks:
            week_end = week_start + dt.timedelta(days=6)
            if week_end >= today:
                continue
            range_start = max(self.start_date, week_start)
            range_end = min(effective_end, week_end)
            self._uneed_add_daily_range(rows, seen, range_start, range_end, daily_dates)
            if len(rows) >= self.args.limit:
                break
        return rows

    def _uneed_add_weekly_rows(
        self,
        rows: list[dict[str, Any]],
        seen: set[str],
        week_start: dt.date,
        range_start: dt.date,
        range_end: dt.date,
    ) -> None:
        week = week_start.isoformat()
        url = "https://www.uneed.best/api/tools/get-archives?" + urllib.parse.urlencode({
            "type": "weekly",
            "date": week,
            "year": week,
        })
        data = self._uneed_get_api(url)
        if not isinstance(data, list):
            return
        for idx, product in enumerate(data, 1):
            votes = [vote for vote in product.get("votes") or [] if isinstance(vote, dict)]
            vote_dates = sorted(filter(None, (date_only(str(vote.get("created_at") or "")) for vote in votes)))
            launch_date = vote_dates[0] if vote_dates else ""
            if not launch_date:
                continue
            parsed_launch_date = dt.date.fromisoformat(launch_date)
            if not range_start <= parsed_launch_date <= range_end:
                continue
            self._uneed_add_product(
                rows,
                seen,
                product,
                idx,
                launch_date,
                "inferred_from_first_vote",
                "weekly_archive_api",
                week_start=week,
            )
            if len(rows) >= self.args.limit:
                return

    def _uneed_add_daily_range(
        self,
        rows: list[dict[str, Any]],
        seen: set[str],
        range_start: dt.date,
        range_end: dt.date,
        daily_dates: set[dt.date],
    ) -> None:
        dates: list[dt.date] = []
        current = range_end
        while current >= range_start:
            if current not in daily_dates:
                daily_dates.add(current)
                dates.append(current)
            current -= dt.timedelta(days=1)

        def fetch_day(current_day: dt.date) -> tuple[str, Any]:
            day = current_day.isoformat()
            url = "https://www.uneed.best/api/tools/get-ladder?" + urllib.parse.urlencode({
                "type": "daily",
                "date": day,
                "year": day,
            })
            return day, self._uneed_get_api(url)

        with ThreadPoolExecutor(max_workers=min(4, len(dates) or 1)) as executor:
            daily_payloads = list(executor.map(fetch_day, dates))

        for day, data in daily_payloads:
            if isinstance(data, list):
                for idx, product in enumerate(data, 1):
                    self._uneed_add_product(
                        rows,
                        seen,
                        product,
                        idx,
                        day,
                        "known_launch_date",
                        "daily_api",
                    )
                    if len(rows) >= self.args.limit:
                        return

    def _uneed_add_product(
        self,
        rows: list[dict[str, Any]],
        seen: set[str],
        product: dict[str, Any],
        rank: int,
        launch_date: str,
        date_confidence: str,
        parser: str,
        *,
        week_start: str = "",
    ) -> None:
        slug = str(product.get("slug") or "")
        title = str(product.get("name") or "").strip()
        if not slug or not title or slug in seen:
            return
        if self.query and not self._uneed_matches_query(product):
            return
        votes = [vote for vote in product.get("votes") or [] if isinstance(vote, dict)]
        vote_score = float(product.get("totalVoteValue") or 0)
        if not vote_score:
            vote_score = sum(float(vote.get("value") or 1) for vote in votes)
        seen.add(slug)
        signals = {
            "id": product.get("id"),
            "slug": slug,
            "rank": rank,
            "votes": len(votes),
            "vote_score": vote_score,
            "reviews": len(product.get("reviews") or []),
            "rate": product.get("rate"),
            "premium": product.get("premium", False),
            "parser": parser,
        }
        if week_start:
            signals["week_start"] = week_start
            signals["date_basis"] = "earliest_vote_created_at"
        rows.append(item(
            "uneed",
            title,
            f"https://www.uneed.best/tool/{urllib.parse.quote(slug)}",
            kind="product",
            summary=str(product.get("description") or ""),
            score=vote_score or float(max(1, 50 - rank)),
            published_at=launch_date,
            product_launch_date=launch_date,
            launch_date=launch_date,
            evidence_published_at=launch_date,
            date_confidence=date_confidence,
            signals=signals,
            raw=product,
        ))

    def _uneed_matches_query(self, product: dict[str, Any]) -> bool:
        tags = product.get("Tags") or product.get("tags") or []
        tag_text = " ".join(
            str(tag.get("name") or tag.get("slug") or "") if isinstance(tag, dict) else str(tag)
            for tag in tags
        )
        return self._query_matches_text(" ".join((
            str(product.get("name") or ""),
            str(product.get("description") or ""),
            tag_text,
        )))

    def _uneed_get_api(self, url: str) -> Any:
        last_error: Exception | None = None
        for _ in range(2):
            try:
                return get_json(url, headers={"Accept": "application/json", "User-Agent": DEFAULT_UA}, timeout=30)
            except Exception as exc:
                last_error = exc
        if last_error:
            return []
        return []

    def _uneed_rows(self, text: str, parser: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, label in re.findall(r'href="(/tool/[^"]+)"[^>]*>(.*?)</a>', text, flags=re.S):
            title = html.unescape(re.sub("<[^>]+>", " ", label))
            title = re.sub(r"\s+", " ", title).strip()
            slug = href.rstrip("/").split("/")[-1]
            if not title or len(title) > 120 or slug in seen:
                continue
            if self.query and not self._query_matches_text(title):
                continue
            seen.add(slug)
            rows.append(item(
                "uneed",
                title,
                f"https://www.uneed.best{href}",
                kind="product",
                summary="",
                score=float(max(1, 30 - len(rows))),
                evidence_published_at=self.today,
                date_confidence="evidence_date_only",
                signals={"slug": slug, "parser": parser, "date_basis": "page_evidence"},
            ))
        return rows

    def _directory_matches_query(self, product: dict[str, Any], keys: tuple[str, ...]) -> bool:
        return self._query_matches_text(" ".join(str(product.get(key) or "") for key in keys))

    def _query_matches_text(self, text: str) -> bool:
        query_terms = [
            term
            for term in re.findall(r"[a-z0-9]+", self.query.lower())
            if (len(term) > 2 or term == "ai") and term not in {"new", "product", "products", "tool", "tools", "app", "apps"}
        ]
        if not query_terms:
            return True
        haystack = text.lower()
        return any(re.search(r"\bai\b", haystack) if term == "ai" else term in haystack for term in query_terms)
