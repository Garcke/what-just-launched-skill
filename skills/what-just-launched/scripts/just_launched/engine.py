"""Core orchestration for What Just Launched."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import urllib.error
from typing import Any

from .common import (
    CONFIG_FILE,
    LEGACY_CONFIG_FILE,
    append_config,
    env_file_keys,
    load_env_file,
    now_utc,
    parse_date,
    status,
)
from .entities import build_products
from .feedback_summary import summarize_feedback
from .ranking import RRF_K, RankingMixin
from .sources.community_feedback.feedback import FeedbackSources
from .sources.community_feedback.hacker_news import HackerNewsSource
from .sources.community_feedback.web_search import WebSearchSource
from .sources.product_data.app_stores import AppStoreSources
from .sources.product_data.directories import DirectorySources
from .sources.product_data.github import GitHubSources
from .sources.product_data.product_hunt import ProductHuntSource
from .sources.registry import selected_sources, source_runner, source_type

class ProductScout(RankingMixin, ProductHuntSource, AppStoreSources, HackerNewsSource, GitHubSources, DirectorySources, FeedbackSources, WebSearchSource):
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.market = args.market.lower()
        self.end_date = parse_date(args.until) or now_utc().date()
        self.start_date = parse_date(args.since) or (self.end_date - dt.timedelta(days=max(1, int(args.days)) - 1))
        if self.start_date > self.end_date:
            raise ValueError("--since cannot be after --until")
        self.days = max(1, (self.end_date - self.start_date).days + 1)
        self.query = args.query.strip()
        self.today = now_utc().date().isoformat()

    def preflight(self) -> list[dict[str, str]]:
        checks = [
            status("product_hunt", "available" if os.getenv("PRODUCT_HUNT_TOKEN") else "missing_config", "set PRODUCT_HUNT_TOKEN for Product Hunt GraphQL"),
            status("appark", "available", "uses public top-charts endpoint with browser User-Agent"),
            status("hacker_news", "available", "uses free HN Algolia API"),
            status("github_trending", "available", "scrapes public GitHub Trending page"),
            status("apple_rss_itunes", "available", "uses Apple RSS and iTunes Search APIs"),
            status("google_play_appbrain", "available", "uses AppBrain page search as a lightweight Android discovery fallback"),
            status("betalist", "available", "scrapes public BetaList pages at low request volume"),
            status("ai_directory", "available", "scrapes public AI directory pages at low request volume"),
            status("reddit", "available" if self._has_reddit_oauth() else "missing_config", "use REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT; public fallback is disabled by default"),
            status("x_twitter", "available" if self._has_x_config() else "missing_config", "set XQUIK_API_KEY, XAI_API_KEY, PRODUCT_SCOUT_X_ADAPTER_COMMAND, FROM_BROWSER=auto, or AUTH_TOKEN+CT0"),
            status("youtube", "available" if os.getenv("YOUTUBE_API_KEY") else "missing_config", "set YOUTUBE_API_KEY; yt-dlp is optional for transcripts"),
            status("web_search", "available", "uses PRODUCT_SCOUT_WEB_PROVIDERS; supports Brave, Exa, DuckDuckGo, Serper, Tavily"),
        ]
        return checks

    def diagnose(self) -> dict[str, Any]:
        return {
            "config_file": str(CONFIG_FILE),
            "config_file_exists": CONFIG_FILE.exists(),
            "legacy_config_file": str(LEGACY_CONFIG_FILE),
            "legacy_config_file_exists": LEGACY_CONFIG_FILE.exists(),
            "config_file_keys": env_file_keys(),
            "credentials": {
                "PRODUCT_HUNT_TOKEN": bool(os.getenv("PRODUCT_HUNT_TOKEN")),
                "REDDIT_CLIENT_ID": bool(os.getenv("REDDIT_CLIENT_ID")),
                "REDDIT_CLIENT_SECRET": bool(os.getenv("REDDIT_CLIENT_SECRET")),
                "REDDIT_USER_AGENT": bool(os.getenv("REDDIT_USER_AGENT")),
                "XQUIK_API_KEY": bool(os.getenv("XQUIK_API_KEY")),
                "XAI_API_KEY": bool(os.getenv("XAI_API_KEY")),
                "PRODUCT_SCOUT_X_ADAPTER_COMMAND": bool(os.getenv("PRODUCT_SCOUT_X_ADAPTER_COMMAND")),
                "AUTH_TOKEN": bool(os.getenv("AUTH_TOKEN")),
                "CT0": bool(os.getenv("CT0")),
                "YOUTUBE_API_KEY": bool(os.getenv("YOUTUBE_API_KEY")),
                "BRAVE_API_KEY": bool(os.getenv("BRAVE_API_KEY")),
                "EXA_API_KEY": bool(os.getenv("EXA_API_KEY")),
                "SERPER_API_KEY": bool(os.getenv("SERPER_API_KEY")),
                "TAVILY_API_KEY": bool(os.getenv("TAVILY_API_KEY")),
                "PRODUCT_SCOUT_WEB_PROVIDERS": os.getenv("PRODUCT_SCOUT_WEB_PROVIDERS", "brave,exa,serper,tavily,duckduckgo"),
            },
            "commands": {
                "yt-dlp": self._command_exists("yt-dlp"),
                "gh": self._command_exists("gh"),
            },
            "preflight": self.preflight(),
        }

    def run(self) -> dict[str, Any]:
        selected = selected_sources(
            self.args.mode,
            self.args.sources,
            self.args.product_sources,
            self.args.feedback_sources,
        )
        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for source in selected:
            fn = source_runner(self, source)
            if not fn:
                errors.append(status(source, "unknown_source", "not registered"))
                continue
            try:
                results.extend(fn())
            except urllib.error.HTTPError as exc:
                errors.append(status(source, f"http_{exc.code}", exc.reason or "HTTP error"))
            except Exception as exc:  # Keep one bad source from killing the whole search.
                errors.append(status(source, "error", f"{type(exc).__name__}: {exc}"))
        if self.args.filter_launch_date:
            results = [
                row
                for row in results
                if (
                    not (row.get("launch_date") or row.get("product_launch_date"))
                    or self._date_in_range(str(row.get("launch_date") or row.get("product_launch_date") or ""))
                )
            ]
        if not self.args.include_raw:
            for row in results:
                row.pop("raw", None)
        ranked_results = self._rank_results(results)
        product_data = self._filter_ranked_results(ranked_results, "product_data")
        community_feedback = self._filter_ranked_results(ranked_results, "community_feedback")
        products = build_products(product_data, community_feedback, self.args.limit)
        return {
            "query": self.query,
            "mode": self.args.mode,
            "market": self.market,
            "days": self.days,
            "selected_sources": selected,
            "time_range": {"since": self.start_date.isoformat(), "until": self.end_date.isoformat()},
            "generated_at": now_utc().isoformat(),
            "preflight": self.preflight(),
            "errors": errors,
            "ranking_model": {
                "name": "source-normalized-weighted-rrf",
                "rrf_k": RRF_K,
                "formula": "0.35*rrf + 0.25*local_relevance + 0.15*freshness + 0.10*source_quality + 0.10*engagement + 0.05*source_diversity",
                "product_formula": "0.45*ranking_strength + 0.20*source_coverage + 0.15*feedback_strength + 0.10*evidence_depth + 0.10*launch_confidence",
            },
            "products": products,
            "product_data": product_data[: self.args.limit],
            "community_feedback": community_feedback[: self.args.limit],
            "community_feedback_summary": summarize_feedback(community_feedback),
            "results": ranked_results[: self.args.limit],
        }

    def _filter_ranked_results(self, rows: list[dict[str, Any]], expected_type: str) -> list[dict[str, Any]]:
        return [
            row
            for row in rows
            if source_type(str(row.get("source") or "")) == expected_type
        ]

    def _date_in_range(self, value: str) -> bool:
        parsed = parse_date(value)
        if not parsed:
            return False
        return self.start_date <= parsed <= self.end_date

    def _safe_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _command_exists(self, command: str) -> bool:
        exe = "where.exe" if os.name == "nt" else "which"
        try:
            completed = subprocess.run([exe, command], capture_output=True, text=True, timeout=5)
            return completed.returncode == 0
        except Exception:
            return False

