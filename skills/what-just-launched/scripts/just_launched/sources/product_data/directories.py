from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import urllib.parse
from typing import Any

from ...common import (
    BROWSER_UA,
    DEFAULT_UA,
    date_only,
    get_json,
    get_page_text,
    get_text,
    item,
)

class DirectorySources:
    def betalist(self) -> list[dict[str, Any]]:
        url = "https://betalist.com/"
        if self.query:
            url = f"https://betalist.com/search?q={urllib.parse.quote_plus(self.query)}"
        text, parser = get_page_text(url, env_flag="PRODUCT_SCOUT_BETALIST_USE_FIRECRAWL")
        rows = self._betalist_rows(text, parser)
        if not rows and parser in {"firecrawl_scrape", "firecrawl_keyless"}:
            text = get_text(url, headers={"User-Agent": BROWSER_UA}, timeout=30)
            rows = self._betalist_rows(text, "html")
        return rows[: self.args.limit]

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
        if not products and parser in {"firecrawl_scrape", "firecrawl_keyless"}:
            text = get_text(url, headers={"User-Agent": BROWSER_UA}, timeout=30)
            parser = "html"
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
            if len(term) > 2 and term not in {"new", "product", "products", "tool", "tools", "app", "apps"}
        ]
        if not query_terms:
            return True
        haystack = " ".join(
            str(product.get(key) or "")
            for key in ("codename", "problem_label", "solution_label", "market", "product_type", "offer_type", "stage")
        ).lower()
        return any(term in haystack for term in query_terms)

    def fazier(self) -> list[dict[str, Any]]:
        products = self._fazier_api_products()
        parser = "next_data_json" if products else ""
        url = "https://fazier.com/"
        if not products:
            text, parser = get_page_text(url, env_flag="PRODUCT_SCOUT_FAZIER_USE_FIRECRAWL")
            products = self._fazier_products(text)
        if not products and parser in {"firecrawl_scrape", "firecrawl_keyless"}:
            text = get_text(url, headers={"User-Agent": BROWSER_UA}, timeout=30)
            parser = "html"
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
        if not rows and parser in {"firecrawl_scrape", "firecrawl_keyless"}:
            text = get_text(url, headers={"User-Agent": BROWSER_UA}, timeout=30)
            rows = self._uneed_rows(text, "html")
        return rows[: self.args.limit]

    def _uneed_api_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        current = self.end_date
        while current >= self.start_date and len(rows) < self.args.limit:
            day = current.isoformat()
            url = "https://www.uneed.best/api/tools/get-ladder?" + urllib.parse.urlencode({
                "type": "daily",
                "date": day,
                "year": day,
            })
            data = self._uneed_get_ladder(url)
            if not isinstance(data, list):
                break
            for idx, product in enumerate(data, 1):
                slug = str(product.get("slug") or "")
                title = str(product.get("name") or "").strip()
                if not slug or not title or slug in seen:
                    continue
                if self.query and not self._directory_matches_query(product, ("name", "description")):
                    continue
                votes = product.get("votes") or []
                vote_score = sum(float(vote.get("value") or 1) for vote in votes if isinstance(vote, dict))
                review_count = len(product.get("reviews") or [])
                seen.add(slug)
                rows.append(item(
                    "uneed",
                    title,
                    f"https://www.uneed.best/tool/{urllib.parse.quote(slug)}",
                    kind="product",
                    summary=str(product.get("description") or ""),
                    score=vote_score or float(max(1, 50 - idx)),
                    published_at=day,
                    product_launch_date=day,
                    launch_date=day,
                    evidence_published_at=day,
                    date_confidence="known_launch_date",
                    signals={
                        "id": product.get("id"),
                        "slug": slug,
                        "rank": idx,
                        "votes": len(votes),
                        "vote_score": vote_score,
                        "reviews": review_count,
                        "rate": product.get("rate"),
                        "premium": product.get("premium", False),
                        "parser": "api",
                    },
                    raw=product,
                ))
                if len(rows) >= self.args.limit:
                    break
            current = current - dt.timedelta(days=1)
        return rows

    def _uneed_get_ladder(self, url: str) -> Any:
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
            if len(term) > 2 and term not in {"new", "product", "products", "tool", "tools", "app", "apps"}
        ]
        if not query_terms:
            return True
        haystack = text.lower()
        return any(term in haystack for term in query_terms)
