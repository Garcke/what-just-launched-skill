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
    "appark": SourceSpec("appark", "appark", ("discovery", "all"), "product_data"),
    "github_trending": SourceSpec("github_trending", "github_trending", ("discovery", "all"), "product_data"),
    "apple": SourceSpec("apple", "apple", ("discovery", "all"), "product_data"),
    "google_play": SourceSpec("google_play", "google_play", ("discovery", "all"), "product_data"),
    "betalist": SourceSpec("betalist", "betalist", ("discovery", "all"), "product_data"),
    "ai_directory": SourceSpec("ai_directory", "ai_directory", ("discovery", "all"), "product_data"),
}

COMMUNITY_FEEDBACK_SPECS = {
    "hacker_news": SourceSpec("hacker_news", "hacker_news", ("discovery", "feedback", "all"), "community_feedback"),
    "reddit": SourceSpec("reddit", "reddit", ("feedback", "all"), "community_feedback"),
    "x": SourceSpec("x", "x_twitter", ("feedback", "all"), "community_feedback"),
    "youtube": SourceSpec("youtube", "youtube", ("feedback", "all"), "community_feedback"),
    "web": SourceSpec("web", "web_search", ("feedback", "all"), "community_feedback"),
}

SOURCE_SPECS = {**PRODUCT_DATA_SPECS, **COMMUNITY_FEEDBACK_SPECS}


def selected_sources(mode: str, requested: str) -> list[str]:
    if requested != "all":
        return [source.strip() for source in requested.split(",") if source.strip()]
    return [source_id for source_id, spec in SOURCE_SPECS.items() if mode in spec.modes]


def source_runner(instance: Any, source_id: str) -> Callable[[], list[dict[str, Any]]] | None:
    spec = SOURCE_SPECS.get(source_id)
    if not spec:
        return None
    runner = getattr(instance, spec.method_name, None)
    return runner if callable(runner) else None
