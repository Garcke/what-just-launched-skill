from __future__ import annotations

import html
import re
from typing import Any

from ...common import (
    BROWSER_UA,
    get_page_text,
    get_text,
    item,
)

class GitHubSources:
    def github_trending(self) -> list[dict[str, Any]]:
        since = "daily" if self.days <= 2 else "weekly" if self.days <= 14 else "monthly"
        url = f"https://github.com/trending?since={since}"
        text, parser = get_page_text(url, env_flag="PRODUCT_SCOUT_GITHUB_TRENDING_USE_FIRECRAWL")
        rows = self._github_trending_rows(text, since, parser)
        if not rows and parser == "firecrawl_scrape":
            text = get_text(url, headers={"User-Agent": BROWSER_UA}, timeout=30)
            rows = self._github_trending_rows(text, since, "html")
        return rows

    def _github_trending_rows(self, text: str, since: str, parser: str) -> list[dict[str, Any]]:
        rows = []
        for block in re.findall(r"<article[^>]*>(.*?)</article>", text, flags=re.S):
            heading = re.search(r'<h2[^>]*class="[^"]*lh-condensed[^"]*"[^>]*>(.*?)</h2>', block, flags=re.S)
            m = re.search(r'href="/([^"/]+/[^"/]+)"', heading.group(1), flags=re.S) if heading else None
            if not m:
                continue
            repo_path = "/" + html.unescape(m.group(1)).strip("/")
            title = repo_path.strip("/").replace("\n", "").replace(" ", "")
            desc_m = re.search(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', block, flags=re.S)
            stars_m = re.search(r'(\d[\d,]*) stars today|(\d[\d,]*) stars this week|(\d[\d,]*) stars this month', block)
            stars = next((int(x.replace(",", "")) for x in (stars_m.groups() if stars_m else []) if x), 0)
            desc = html.unescape(re.sub("<[^>]+>", "", desc_m.group(1))).strip() if desc_m else ""
            rows.append(item(
                "github_trending",
                title,
                f"https://github.com{repo_path}",
                kind="repository",
                summary=desc,
                score=float(stars),
                evidence_published_at=self.today,
                date_confidence="trending_period_only",
                signals={"stars_period": stars, "since": since, "date_basis": "trending_period", "parser": parser},
            ))
        return rows

