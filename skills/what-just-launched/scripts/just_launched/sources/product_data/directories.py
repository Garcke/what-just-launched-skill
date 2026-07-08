from __future__ import annotations

import html
import re
import urllib.parse
from typing import Any

from ...common import (
    BROWSER_UA,
    get_text,
    item,
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
