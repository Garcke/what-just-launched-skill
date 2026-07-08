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

class WebSearchSource:
    def web_search(self) -> list[dict[str, Any]]:
        providers = [
            p.strip().lower()
            for p in os.getenv("PRODUCT_SCOUT_WEB_PROVIDERS", "serpapi,exa,tavily,duckduckgo").split(",")
            if p.strip()
        ]
        errors: list[str] = []
        collected: list[dict[str, Any]] = []
        for provider in providers:
            try:
                if provider in ("serpapi", "serpapi_google") and os.getenv("SERPAPI_API_KEY"):
                    rows = self._serpapi_search()
                elif provider == "exa" and os.getenv("EXA_API_KEY"):
                    rows = self._exa_search()
                elif provider == "tavily" and os.getenv("TAVILY_API_KEY"):
                    rows = self._tavily_search()
                elif provider in ("duckduckgo", "ddg"):
                    rows = self._duckduckgo_search()
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

    def _serpapi_search(self) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode({
            "engine": "google",
            "q": self.query,
            "api_key": os.environ["SERPAPI_API_KEY"],
            "num": min(self.args.limit, 20),
            "hl": self._serpapi_language(),
            "gl": self.market.lower(),
            "tbs": self._serpapi_time_filter(),
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

    def _exa_search(self) -> list[dict[str, Any]]:
        payload = json.dumps({"query": self.query, "numResults": min(self.args.limit, 20), "startPublishedDate": self.start_date.isoformat(), "endPublishedDate": self.end_date.isoformat()}).encode()
        req = urllib.request.Request(
            "https://api.exa.ai/search",
            data=payload,
            headers={"x-api-key": os.environ["EXA_API_KEY"], "Content-Type": "application/json", "User-Agent": DEFAULT_UA},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        rows = []
        for r in data.get("results", []):
            rows.append(item("exa_search", r.get("title", ""), r.get("url", ""), kind="web_result", summary=r.get("text", "")[:500], score=10, raw=r))
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

    def _duckduckgo_search(self) -> list[dict[str, Any]]:
        if not self.query:
            return []
        time.sleep(float(os.getenv("PRODUCT_SCOUT_DDG_DELAY", "1.0")))
        params = urllib.parse.urlencode({"q": self.query, "kl": self._ddg_region(), "df": self._ddg_time_filter()})
        text = get_text(
            f"https://html.duckduckgo.com/html/?{params}",
            headers={
                "User-Agent": BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=25,
        )
        rows = []
        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'(?:<a[^>]+class="result__snippet"[^>]*>|<div[^>]+class="result__snippet"[^>]*>)(.*?)</(?:a|div)>',
            flags=re.S,
        )
        for idx, m in enumerate(pattern.finditer(text), 1):
            href = html.unescape(m.group(1))
            title = html.unescape(re.sub("<[^>]+>", "", m.group(2))).strip()
            snippet = html.unescape(re.sub("<[^>]+>", "", m.group(3))).strip()
            url = self._normalize_ddg_url(href)
            rows.append(item(
                "duckduckgo",
                title,
                url,
                kind="web_result",
                summary=snippet,
                score=max(1, 30 - idx),
                signals={"position": idx, "region": self._ddg_region(), "time_filter": self._ddg_time_filter()},
            ))
            if len(rows) >= min(self.args.limit, 20):
                break
        return rows

    def _serpapi_language(self) -> str:
        mapping = {"cn": "zh-cn", "jp": "ja", "kr": "ko", "de": "de", "fr": "fr"}
        return mapping.get(self.market, "en")

    def _serpapi_time_filter(self) -> str:
        if self.days <= 1:
            return "qdr:d"
        if self.days <= 7:
            return "qdr:w"
        if self.days <= 31:
            return "qdr:m"
        return "qdr:y"

    def _normalize_ddg_url(self, href: str) -> str:
        if href.startswith("//duckduckgo.com/l/?"):
            query = urllib.parse.parse_qs(urllib.parse.urlparse("https:" + href).query)
            if query.get("uddg"):
                return query["uddg"][0]
        if href.startswith("/l/?"):
            query = urllib.parse.parse_qs(urllib.parse.urlparse("https://duckduckgo.com" + href).query)
            if query.get("uddg"):
                return query["uddg"][0]
        return href

    def _ddg_region(self) -> str:
        mapping = {
            "us": "us-en",
            "cn": "cn-zh",
            "jp": "jp-jp",
            "kr": "kr-kr",
            "gb": "uk-en",
            "uk": "uk-en",
            "de": "de-de",
            "fr": "fr-fr",
        }
        return os.getenv("PRODUCT_SCOUT_DDG_REGION", mapping.get(self.market, "wt-wt"))

    def _ddg_time_filter(self) -> str:
        if self.days <= 1:
            return "d"
        if self.days <= 7:
            return "w"
        if self.days <= 31:
            return "m"
        return "y"

