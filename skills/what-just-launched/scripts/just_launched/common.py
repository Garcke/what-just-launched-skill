"""Shared utilities for the What Just Launched runtime."""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(os.getenv("PRODUCT_SCOUT_CONFIG_DIR", os.getenv("WHAT_JUST_LAUNCHED_CONFIG_DIR", "~/.config/what-just-launched"))).expanduser()
CONFIG_FILE = CONFIG_DIR / ".env"
LEGACY_CONFIG_FILE = Path("~/.config/product-scout/.env").expanduser()
DEFAULT_UA = os.getenv(
    "PRODUCT_SCOUT_USER_AGENT",
    "windows:product-scout:0.1.0 (by /u/configure-product-scout)",
)
BROWSER_UA = os.getenv(
    "PRODUCT_SCOUT_BROWSER_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
)
def load_env_file(path: Path = CONFIG_FILE) -> dict[str, str]:
    loaded: dict[str, str] = {}
    if path == CONFIG_FILE and not path.exists() and LEGACY_CONFIG_FILE.exists():
        path = LEGACY_CONFIG_FILE
    if not path.exists():
        return loaded
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


def env_file_keys(path: Path = CONFIG_FILE) -> list[str]:
    if path == CONFIG_FILE and not path.exists() and LEGACY_CONFIG_FILE.exists():
        path = LEGACY_CONFIG_FILE
    if not path.exists():
        return []
    keys: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.append(line.split("=", 1)[0].strip())
    return sorted(k for k in keys if k)


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:3] + "*" * (len(value) - 6) + value[-3:]


def append_config(entries: dict[str, str], path: Path = CONFIG_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    existing_keys = set()
    for line in existing.splitlines():
        if "=" in line and not line.strip().startswith("#"):
            existing_keys.add(line.split("=", 1)[0].strip())
    with path.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        for key, value in entries.items():
            if key in existing_keys:
                continue
            f.write(f"{key}={value}\n")


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_days_ago(days: int) -> str:
    return (now_utc() - dt.timedelta(days=days)).date().isoformat()


def epoch_days_ago(days: int) -> int:
    return int((now_utc() - dt.timedelta(days=days)).timestamp())


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(text).date()
    except ValueError:
        pass
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def date_only(value: str | None) -> str:
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else ""


def date_to_epoch_start(value: dt.date) -> int:
    return int(dt.datetime.combine(value, dt.time.min, tzinfo=dt.timezone.utc).timestamp())


def date_to_epoch_end(value: dt.date) -> int:
    return int(dt.datetime.combine(value, dt.time.max, tzinfo=dt.timezone.utc).timestamp())


def get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, timeout: int = 25) -> Any:
    body = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    req_headers.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def get_text(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return raw.decode("utf-8", "replace")


def status(name: str, state: str, reason: str = "") -> dict[str, str]:
    return {"source": name, "status": state, "reason": reason}


def item(
    source: str,
    title: str,
    url: str,
    *,
    kind: str,
    summary: str = "",
    score: float = 0,
    published_at: str = "",
    product_launch_date: str = "",
    signals: dict[str, Any] | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "kind": kind,
        "title": title,
        "url": url,
        "summary": summary,
        "score": score,
        "published_at": published_at,
        "product_launch_date": product_launch_date,
        "signals": signals or {},
        "raw": raw or {},
    }

