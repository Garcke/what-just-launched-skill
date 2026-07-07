from __future__ import annotations

import base64
import datetime as dt
import html
import json
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
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
            for p in os.getenv("PRODUCT_SCOUT_WEB_PROVIDERS", "brave,exa,serper,tavily,google_news,bing_news,duckduckgo").split(",")
            if p.strip()
        ]
        errors: list[str] = []
        collected: list[dict[str, Any]] = []
        for provider in providers:
            try:
                if provider == "brave" and os.getenv("BRAVE_API_KEY"):
                    rows = self._brave_search()
                elif provider == "exa" and os.getenv("EXA_API_KEY"):
                    rows = self._exa_search()
                elif provider == "serper" and os.getenv("SERPER_API_KEY"):
                    rows = self._serper_search()
                elif provider == "tavily" and os.getenv("TAVILY_API_KEY"):
                    rows = self._tavily_search()
                elif provider in ("google_news", "google_news_rss"):
                    rows = self._google_news_rss()
                elif provider in ("bing_news", "bing_news_rss"):
                    rows = self._bing_news_rss()
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
    def _brave_search(self) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode({"q": self.query, "count": min(self.args.limit, 20), "freshness": f"pd{self.days}"})
        data = get_json(
            f"https://api.search.brave.com/res/v1/web/search?{params}",
            headers={"X-Subscription-Token": os.environ["BRAVE_API_KEY"], "Accept": "application/json", "User-Agent": DEFAULT_UA},
        )
        rows = []
        for r in data.get("web", {}).get("results", []):
            rows.append(item("brave_search", r.get("title", ""), r.get("url", ""), kind="web_result", summary=r.get("description", ""), score=10, raw=r))
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

    def _serper_search(self) -> list[dict[str, Any]]:
        data = post_json(
            "https://google.serper.dev/search",
            {"q": self.query, "num": min(self.args.limit, 20)},
            headers={"X-API-KEY": os.environ["SERPER_API_KEY"], "User-Agent": DEFAULT_UA},
        )
        rows = []
        for r in data.get("organic", []):
            rows.append(item(
                "serper_search",
                r.get("title", ""),
                r.get("link", ""),
                kind="web_result",
                summary=r.get("snippet", ""),
                score=10,
                signals={"position": r.get("position")},
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

    def _google_news_rss(self) -> list[dict[str, Any]]:
        if not self.query:
            return []
        params = urllib.parse.urlencode({"q": self.query, "hl": self._news_locale(), "gl": self.market.upper(), "ceid": f"{self.market.upper()}:en"})
        return self._rss_search("google_news", f"https://news.google.com/rss/search?{params}")

    def _bing_news_rss(self) -> list[dict[str, Any]]:
        if not self.query:
            return []
        params = urllib.parse.urlencode({"q": self.query, "cc": self.market.upper(), "setlang": self._news_language()})
        return self._rss_search("bing_news", f"https://www.bing.com/news/search?format=rss&{params}")

    def _rss_search(self, source: str, url: str) -> list[dict[str, Any]]:
        text = get_text(url, headers={"User-Agent": DEFAULT_UA, "Accept": "application/rss+xml,application/xml,text/xml"})
        root = ET.fromstring(text)
        rows = []
        for idx, node in enumerate(root.findall(".//item"), 1):
            title = self._xml_text(node, "title")
            link = self._xml_text(node, "link")
            summary = self._xml_text(node, "description")
            published = self._xml_text(node, "pubDate")
            rows.append(item(
                source,
                title,
                link,
                kind="news_result",
                summary=html.unescape(re.sub("<[^>]+>", "", summary))[:500],
                published_at=published,
                evidence_published_at=published,
                date_confidence="evidence_date_only" if published else "unknown",
                score=max(1, 30 - idx),
                signals={"position": idx, "provider": source},
            ))
            if len(rows) >= min(self.args.limit, 20):
                break
        return rows

    def _xml_text(self, node: ET.Element, tag: str) -> str:
        child = node.find(tag)
        return (child.text or "").strip() if child is not None else ""

    def _news_locale(self) -> str:
        mapping = {"cn": "zh-CN", "jp": "ja", "kr": "ko", "de": "de", "fr": "fr"}
        return mapping.get(self.market, "en-US")

    def _news_language(self) -> str:
        mapping = {"cn": "zh-CN", "jp": "ja-JP", "kr": "ko-KR", "de": "de-DE", "fr": "fr-FR"}
        return mapping.get(self.market, "en-US")

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

