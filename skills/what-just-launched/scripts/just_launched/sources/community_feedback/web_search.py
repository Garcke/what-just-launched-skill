from __future__ import annotations

import datetime as dt
import os
import re
import urllib.parse
from typing import Any

from ...common import (
    DEFAULT_UA,
    date_only,
    get_json,
    item,
    post_json,
)

class WebSearchSource:
    def web_search(self) -> list[dict[str, Any]]:
        providers = [
            p.strip().lower()
            for p in os.getenv("PRODUCT_SCOUT_WEB_PROVIDERS", "brave,serpapi,tavily").split(",")
            if p.strip()
        ]
        errors: list[str] = []
        collected: list[dict[str, Any]] = []
        for provider in providers:
            try:
                if provider == "brave" and self._brave_api_key():
                    rows = self._brave_search()
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
            published_at, date_raw, date_source = self._web_result_date(r, r.get("url", ""))
            if published_at and not self._date_in_range(published_at):
                continue
            result_type, feedback_likelihood = self._classify_web_result(r.get("title", ""), r.get("url", ""), summary)
            rows.append(item(
                "brave_search",
                r.get("title", ""),
                r.get("url", ""),
                kind="web_result",
                summary=summary,
                score=max(1, 30 - idx),
                published_at=published_at,
                evidence_published_at=published_at,
                date_confidence="evidence_date_only" if published_at else "unknown",
                signals={
                    "position": idx,
                    "provider": "brave",
                    "age": r.get("age", ""),
                    "freshness": self._brave_freshness(),
                    "result_type": result_type,
                    "feedback_likelihood": feedback_likelihood,
                    "date_raw": date_raw,
                    "date_source": date_source,
                    "date_verified": bool(published_at),
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
        if data.get("error"):
            raise RuntimeError(str(data.get("error")))
        rows = []
        for idx, r in enumerate(data.get("organic_results", []), 1):
            published_at, date_raw, date_source = self._web_result_date(r, r.get("link", ""))
            if published_at and not self._date_in_range(published_at):
                continue
            result_type, feedback_likelihood = self._classify_web_result(r.get("title", ""), r.get("link", ""), r.get("snippet", ""))
            rows.append(item(
                "serpapi_search",
                r.get("title", ""),
                r.get("link", ""),
                kind="web_result",
                summary=r.get("snippet", ""),
                score=max(1, 30 - idx),
                published_at=published_at,
                evidence_published_at=published_at,
                date_confidence="evidence_date_only" if published_at else "unknown",
                signals={
                    "position": r.get("position") or idx,
                    "provider": "serpapi",
                    "result_type": result_type,
                    "feedback_likelihood": feedback_likelihood,
                    "date_raw": date_raw,
                    "date_source": date_source,
                    "date_verified": bool(published_at),
                },
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
            },
            headers={"User-Agent": DEFAULT_UA},
        )
        rows = []
        for r in data.get("results", []):
            published_at, date_raw, date_source = self._web_result_date(r, r.get("url", ""))
            if published_at and not self._date_in_range(published_at):
                continue
            result_type, feedback_likelihood = self._classify_web_result(r.get("title", ""), r.get("url", ""), r.get("content", ""))
            rows.append(item(
                "tavily_search",
                r.get("title", ""),
                r.get("url", ""),
                kind="web_result",
                summary=r.get("content", ""),
                score=float(r.get("score") or 10),
                published_at=published_at,
                evidence_published_at=published_at,
                date_confidence="evidence_date_only" if published_at else "unknown",
                signals={
                    "provider": "tavily",
                    "result_type": result_type,
                    "feedback_likelihood": feedback_likelihood,
                    "date_raw": date_raw,
                    "date_source": date_source,
                    "date_verified": bool(published_at),
                },
                raw=r,
            ))
        return rows

    def _web_result_date(self, result: dict[str, Any], url: str) -> tuple[str, str, str]:
        for key in ("published_date", "publishedDate", "page_age", "age", "date"):
            raw = str(result.get(key) or "").strip()
            parsed = self._parse_web_date(raw)
            if parsed:
                return parsed, raw, f"provider:{key}"
        match = re.search(r"/(20\d{2})[/_-](0?[1-9]|1[0-2])[/_-](0?[1-9]|[12]\d|3[01])(?:/|[-_.])", url)
        if match:
            try:
                parsed = dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
                return parsed, match.group(0).strip("/"), "url_path"
            except ValueError:
                pass
        return "", "", ""

    def _parse_web_date(self, value: str) -> str:
        if not value:
            return ""
        parsed = date_only(value)
        if parsed:
            return parsed
        lowered = value.lower().strip()
        if lowered == "today":
            return self.end_date.isoformat()
        if lowered == "yesterday":
            return (self.end_date - dt.timedelta(days=1)).isoformat()
        relative = re.search(r"(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago", lowered)
        if relative:
            amount = int(relative.group(1))
            unit = relative.group(2)
            days = amount if unit == "day" else amount * 7 if unit == "week" else amount * 30 if unit == "month" else amount * 365 if unit == "year" else 0
            return (self.end_date - dt.timedelta(days=days)).isoformat()
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                return dt.datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
        return ""

    def _classify_web_result(self, title: str, url: str, summary: str) -> tuple[str, str]:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.lower()
        text = f"{title} {summary}".lower()
        if host in {"reddit.com", "news.ycombinator.com", "lobste.rs", "stackoverflow.com"}:
            return "community_discussion", "high"
        if host in {"x.com", "twitter.com", "linkedin.com", "facebook.com", "youtube.com"}:
            return "social_post", "medium"
        if host in {"prnewswire.com", "businesswire.com", "globenewswire.com", "einpresswire.com"} or "press-release" in path or "press release" in text:
            return "press_release", "low"
        if host in {"producthunt.com", "betalist.com", "peerlist.io", "microlaunch.net", "uneed.best", "fazier.com"}:
            return "launch_listing", "low"
        if re.search(r"\b(review|reviews|reviewed|hands-on|tested|comparison|alternative|alternatives|versus|vs\.?\b)", text):
            return "review_or_comparison", "high"
        if re.search(r"\b(top|best)\s+\d*\s*(ai|apps?|products?|platforms?|tools?)\b", text) or "ranked" in text:
            return "listicle", "low"
        if any(segment in path for segment in ("/terms", "/privacy", "/docs", "/pricing", "/download", "/plugin")):
            return "official_or_product_page", "low"
        if re.search(r"\b(announce|announced|launches|launched|released|funding|raises)\b", text):
            return "news", "medium"
        return "web_page", "low"

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

