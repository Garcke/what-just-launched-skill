"""Source registries and selection rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    method_name: str
    modes: tuple[str, ...]
    source_type: str


PRODUCT_DATA_SPECS = {
    "product_hunt": SourceSpec("product_hunt", "product_hunt", ("discovery", "all"), "product_data"),
    "github_trending": SourceSpec("github_trending", "github_trending", ("discovery", "all"), "product_data"),
    "apple": SourceSpec("apple", "apple", ("discovery", "all"), "product_data"),
    "google_play": SourceSpec("google_play", "google_play", ("discovery", "all"), "product_data"),
    "betalist": SourceSpec("betalist", "betalist", ("discovery", "all"), "product_data"),
    "microlaunch": SourceSpec("microlaunch", "microlaunch", ("discovery", "all"), "product_data"),
    "uneed": SourceSpec("uneed", "uneed", ("discovery", "all"), "product_data"),
    "fazier": SourceSpec("fazier", "fazier", ("discovery", "all"), "product_data"),
}

COMMUNITY_FEEDBACK_SPECS = {
    "hacker_news": SourceSpec("hacker_news", "hacker_news", ("discovery", "feedback", "all"), "community_feedback"),
    "web": SourceSpec("web", "web_search", ("feedback", "all"), "community_feedback"),
    "reddit": SourceSpec("reddit", "reddit", ("feedback", "all"), "community_feedback"),
    "reddit_public": SourceSpec("reddit_public", "reddit_public", (), "community_feedback"),
    "lobsters": SourceSpec("lobsters", "lobsters", (), "community_feedback"),
    "github_issues": SourceSpec("github_issues", "github_issues", ("feedback", "all"), "community_feedback"),
    "stackexchange": SourceSpec("stackexchange", "stackexchange", ("feedback", "all"), "community_feedback"),
    "x": SourceSpec("x", "x_twitter", ("feedback", "all"), "community_feedback"),
    "youtube": SourceSpec("youtube", "youtube", ("feedback", "all"), "community_feedback"),
}

SOURCE_SPECS = {**PRODUCT_DATA_SPECS, **COMMUNITY_FEEDBACK_SPECS}

EMITTED_SOURCE_TYPES = {
    "product_hunt": "product_data",
    "github_trending": "product_data",
    "apple_rss": "product_data",
    "itunes_search": "product_data",
    "appbrain": "product_data",
    "betalist": "product_data",
    "microlaunch": "product_data",
    "uneed": "product_data",
    "fazier": "product_data",
    "brave_search": "community_feedback",
    "serpapi_search": "community_feedback",
    "tavily_search": "community_feedback",
    "web_search": "community_feedback",
    "hacker_news": "community_feedback",
    "reddit": "community_feedback",
    "reddit_public": "community_feedback",
    "lobsters": "community_feedback",
    "github_issues": "community_feedback",
    "stackexchange": "community_feedback",
    "xquik": "community_feedback",
    "x_external": "community_feedback",
    "youtube": "community_feedback",
}


def selected_sources(
    mode: str,
    requested: str,
    product_sources: str = "all",
    feedback_sources: str = "all",
) -> list[str]:
    if requested != "all":
        return [source.strip() for source in requested.split(",") if source.strip()]
    if product_sources != "all" or feedback_sources != "all":
        selected: list[str] = []
        if mode in ("discovery", "all"):
            selected.extend(_selected_by_type(PRODUCT_DATA_SPECS, product_sources, mode))
        if mode in ("feedback", "all"):
            selected.extend(_selected_by_type(COMMUNITY_FEEDBACK_SPECS, feedback_sources, mode))
        return list(dict.fromkeys(selected))
    return [source_id for source_id, spec in SOURCE_SPECS.items() if mode in spec.modes]


def _selected_by_type(specs: dict[str, SourceSpec], requested: str, mode: str) -> list[str]:
    if requested == "all":
        return [source_id for source_id, spec in specs.items() if mode in spec.modes]
    return [source.strip() for source in requested.split(",") if source.strip()]


def source_runner(instance: Any, source_id: str) -> Callable[[], list[dict[str, Any]]] | None:
    spec = SOURCE_SPECS.get(source_id)
    if not spec:
        return None
    runner = getattr(instance, spec.method_name, None)
    return runner if callable(runner) else None


def source_type(source_id: str) -> str:
    spec = SOURCE_SPECS.get(source_id)
    if spec:
        return spec.source_type
    return EMITTED_SOURCE_TYPES.get(source_id, "unknown")
