from __future__ import annotations

import os
import urllib.parse
from typing import Any

from ...common import (
    DEFAULT_UA,
    get_json,
    item,
    post_json,
)

class WebSearchSource:
    def web_search(self) -> list[dict[str, Any]]:
        providers = [
            p.strip().lower()
            for p in os.getenv("PRODUCT_SCOUT_WEB_PROVIDERS", "brave,firecrawl,serpapi,tavily").split(",")
            if p.strip()
        ]
        errors: list[str] = []
        collected: list[dict[str, Any]] = []
        for provider in providers:
            try:
                if provider == "brave" and self._brave_api_key():
                    rows = self._brave_search()
                elif provider == "firecrawl" and os.getenv("FIRECRAWL_API_KEY"):
                    rows = self._firecrawl_search()
                elif provider in ("serpapi", "serpapi_google") and os.getenv("SERPAPI_API_KEY"):
                    rows = self._serpapi_search()
                elif provider == "tavily" and os.getenv("TAVILY_API_KEY"):
                    rows = self._tavily_search()
                else:
                    continue
                if rows:
                    collected.extend(rows)
            except Exception as exc:
                errors.append(f"{provider}: {type(exc).__name__}: {exc}")
                continue
        if collected:
            return collected
        if errors:
            return [item(
                "web_search",
                "All configured web providers failed",
                "",
                kind="source_error",
                summary="; ".join(errors)[:500],
                signals={"providers": providers},
            )]
        return []

    def _brave_search(self) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode({
            "q": self.query,
            "count": min(self.args.limit, 20),
            "country": self.market.lower(),
            "search_lang": self._search_language(),
            "freshness": self._brave_freshness(),
        })
        data = get_json(
            f"https://api.search.brave.com/res/v1/web/search?{params}",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "User-Agent": DEFAULT_UA,
                "X-Subscription-Token": self._brave_api_key() or "",
            },
            timeout=25,
        )
        rows = []
        for idx, r in enumerate(data.get("web", {}).get("results", []), 1):
            snippets = r.get("extra_snippets") or []
            summary_parts = [r.get("description", ""), *snippets[:2]]
            summary = " ".join(part for part in summary_parts if part)
            rows.append(item(
                "brave_search",
                r.get("title", ""),
                r.get("url", ""),
                kind="web_result",
                summary=summary,
                score=max(1, 30 - idx),
                signals={
                    "position": idx,
                    "provider": "brave",
                    "age": r.get("age", ""),
                    "freshness": self._brave_freshness(),
                },
                raw=r,
            ))
        return rows

    def _firecrawl_search(self) -> list[dict[str, Any]]:
        data = post_json(
            "https://api.firecrawl.dev/v2/search",
            {
                "query": self.query,
                "limit": min(self.args.limit, 20),
                "sources": ["web"],
                "country": self.market.upper(),
                "tbs": self._time_filter(),
                "timeout": 60000,
            },
            headers={
                "Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}",
                "User-Agent": DEFAULT_UA,
            },
            timeout=70,
        )
        rows = []
        for idx, r in enumerate(data.get("data", {}).get("web", []), 1):
            summary = r.get("description") or r.get("markdown", "")[:500]
            rows.append(item(
                "firecrawl_search",
                r.get("title", ""),
                r.get("url", ""),
                kind="web_result",
                summary=summary,
                score=max(1, 30 - idx),
                signals={
                    "position": r.get("position") or idx,
                    "provider": "firecrawl",
                    "category": r.get("category", ""),
                },
                raw=r,
            ))
        return rows

    def _serpapi_search(self) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode({
            "engine": "google",
            "q": self.query,
            "api_key": os.environ["SERPAPI_API_KEY"],
            "num": min(self.args.limit, 20),
            "hl": self._search_language(),
            "gl": self.market.lower(),
            "tbs": self._time_filter(),
        })
        data = get_json(
            f"https://serpapi.com/search.json?{params}",
            headers={"Accept": "application/json", "User-Agent": DEFAULT_UA},
        )
        rows = []
        for idx, r in enumerate(data.get("organic_results", []), 1):
            rows.append(item(
                "serpapi_search",
                r.get("title", ""),
                r.get("link", ""),
                kind="web_result",
                summary=r.get("snippet", ""),
                score=max(1, 30 - idx),
                signals={"position": r.get("position") or idx, "provider": "serpapi"},
                raw=r,
            ))
        return rows

    def _tavily_search(self) -> list[dict[str, Any]]:
        data = post_json(
            "https://api.tavily.com/search",
            {
                "api_key": os.environ["TAVILY_API_KEY"],
                "query": self.query,
                "max_results": min(self.args.limit, 20),
                "search_depth": "basic",
                "days": self.days,
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
            },
            headers={"User-Agent": DEFAULT_UA},
        )
        rows = []
        for r in data.get("results", []):
            rows.append(item(
                "tavily_search",
                r.get("title", ""),
                r.get("url", ""),
                kind="web_result",
                summary=r.get("content", ""),
                score=float(r.get("score") or 10),
                raw=r,
            ))
        return rows

    def _brave_api_key(self) -> str:
        return os.getenv("BRAVE_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY") or ""

    def _search_language(self) -> str:
        mapping = {"cn": "zh-cn", "jp": "ja", "kr": "ko", "de": "de", "fr": "fr"}
        return mapping.get(self.market, "en")

    def _time_filter(self) -> str:
        if self.days <= 1:
            return "qdr:d"
        if self.days <= 7:
            return "qdr:w"
        if self.days <= 31:
            return "qdr:m"
        return "qdr:y"

    def _brave_freshness(self) -> str:
        return f"{self.start_date.isoformat()}to{self.end_date.isoformat()}"

