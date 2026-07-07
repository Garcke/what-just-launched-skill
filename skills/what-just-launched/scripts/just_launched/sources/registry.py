"""Source registry and selection rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    method_name: str
    modes: tuple[str, ...]


SOURCE_SPECS = {
    "product_hunt": SourceSpec("product_hunt", "product_hunt", ("discovery", "all")),
    "appark": SourceSpec("appark", "appark", ("discovery", "all")),
    "hacker_news": SourceSpec("hacker_news", "hacker_news", ("discovery", "feedback", "all")),
    "github_trending": SourceSpec("github_trending", "github_trending", ("discovery", "all")),
    "apple": SourceSpec("apple", "apple", ("discovery", "all")),
    "google_play": SourceSpec("google_play", "google_play", ("discovery", "all")),
    "betalist": SourceSpec("betalist", "betalist", ("discovery", "all")),
    "ai_directory": SourceSpec("ai_directory", "ai_directory", ("discovery", "all")),
    "reddit": SourceSpec("reddit", "reddit", ("feedback", "all")),
    "x": SourceSpec("x", "x_twitter", ("feedback", "all")),
    "youtube": SourceSpec("youtube", "youtube", ("feedback", "all")),
    "web": SourceSpec("web", "web_search", ("feedback", "all")),
}


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
