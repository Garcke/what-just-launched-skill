from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
from typing import Any

from ...common import (
    BROWSER_UA,
    date_only,
    firecrawl_scrape,
    get_text,
    item,
)

class DirectorySources:
    def betalist(self) -> list[dict[str, Any]]:
        url = "https://betalist.com/"
        if self.query:
            url = f"https://betalist.com/search?q={urllib.parse.quote_plus(self.query)}"
        text = get_text(url, headers={"User-Agent": BROWSER_UA})
        rows = []
        for m in re.finditer(r'<a[^>]+href="(/startups/[^"]+)"[^>]*>(.*?)</a>', text, flags=re.S):
            title = html.unescape(re.sub("<[^>]+>", "", m.group(2))).strip()
            if title and len(title) < 120:
                rows.append(item("betalist", title, f"https://betalist.com{m.group(1)}", kind="startup", score=20))
        return rows[: self.args.limit]

    def microlaunch(self) -> list[dict[str, Any]]:
        url = "https://microlaunch.net/"
        text, parser = self._microlaunch_page_text(url)
        products = self._microlaunch_products(text)
        if not products and parser == "firecrawl_scrape":
            text = get_text(url, headers={"User-Agent": BROWSER_UA}, timeout=30)
            parser = "html"
            products = self._microlaunch_products(text)
        rows = []
        for idx, product in enumerate(products, 1):
            title = str(product.get("codename") or "").strip()
            slug = str(product.get("slug") or "").strip()
            created_at = str(product.get("created_at") or "").strip()
            summary = str(product.get("problem_label") or product.get("solution_label") or "").strip()
            if not title or not slug:
                continue
            if self.query and not self._microlaunch_matches_query(product):
                continue
            rows.append(item(
                "microlaunch",
                title,
                f"https://microlaunch.net/p/{urllib.parse.quote(slug)}",
                kind="product",
                summary=summary,
                score=float(max(1, 40 - idx)),
                published_at=created_at,
                product_launch_date=date_only(created_at),
                launch_date=date_only(created_at),
                evidence_published_at=created_at,
                date_confidence="known_launch_date" if created_at else "unknown",
                signals={
                    "id": product.get("id"),
                    "slug": slug,
                    "market": product.get("market", ""),
                    "product_type": product.get("product_type", ""),
                    "offer_type": product.get("offer_type", ""),
                    "stage": product.get("stage", ""),
                    "is_premium": product.get("is_premium", False),
                    "parser": parser,
                },
                raw=product,
            ))
            if len(rows) >= self.args.limit:
                break
        return rows

    def _microlaunch_page_text(self, url: str) -> tuple[str, str]:
        if os.getenv("FIRECRAWL_API_KEY") and os.getenv("PRODUCT_SCOUT_MICROLAUNCH_USE_FIRECRAWL", "true").lower() not in {"0", "false", "no"}:
            try:
                data = firecrawl_scrape(url, formats=["html", "markdown"], only_main_content=False)
                body = data.get("data", {}) if isinstance(data, dict) else {}
                text = "\n".join(str(body.get(key) or "") for key in ("html", "markdown") if body.get(key))
                if text:
                    return text, "firecrawl_scrape"
            except Exception:
                pass
        return get_text(url, headers={"User-Agent": BROWSER_UA}, timeout=30), "html"

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
