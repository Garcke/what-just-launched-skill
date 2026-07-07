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

from ..common import (
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
    def ai_directory(self) -> list[dict[str, Any]]:
        url = "https://theresanaiforthat.com/"
        if self.query:
            url = f"https://theresanaiforthat.com/s/{urllib.parse.quote_plus(self.query)}/"
        text = get_text(url, headers={"User-Agent": BROWSER_UA})
        rows = []
        for m in re.finditer(r'<a[^>]+href="(/ai/[^"]+)"[^>]*>(.*?)</a>', text, flags=re.S):
            title = html.unescape(re.sub("<[^>]+>", "", m.group(2))).strip()
            if title and len(title) < 120:
                rows.append(item("ai_directory", title, f"https://theresanaiforthat.com{m.group(1)}", kind="ai_tool", score=15))
        return rows[: self.args.limit]

