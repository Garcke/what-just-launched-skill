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

class FeedbackSources:
    def reddit(self) -> list[dict[str, Any]]:
        if not self._has_reddit_oauth():
            if os.getenv("PRODUCT_SCOUT_ALLOW_REDDIT_PUBLIC_JSON", "").lower() == "true":
                return self._reddit_public_low_rate()
            return []
        token = self._reddit_token()
        params = urllib.parse.urlencode({"q": self.query, "sort": "relevance", "t": "month", "limit": min(self.args.limit, 25), "type": "link"})
        data = get_json(
            f"https://oauth.reddit.com/search?{params}",
            headers={"Authorization": f"Bearer {token}", "User-Agent": os.getenv("REDDIT_USER_AGENT", DEFAULT_UA)},
        )
        rows = []
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            row = item(
                "reddit",
                d.get("title", ""),
                "https://www.reddit.com" + d.get("permalink", ""),
                kind="discussion",
                summary=d.get("selftext", "")[:500],
                published_at=dt.datetime.fromtimestamp(d.get("created_utc", 0), dt.timezone.utc).isoformat() if d.get("created_utc") else "",
                score=float(d.get("score") or 0) + float(d.get("num_comments") or 0) * 2,
                signals={"subreddit": d.get("subreddit"), "upvotes": d.get("score"), "comments": d.get("num_comments")},
                raw=d,
            )
            row["id"] = d.get("id")
            row["permalink"] = d.get("permalink")
            rows.append(row)
        if os.getenv("PRODUCT_SCOUT_REDDIT_COMMENTS", "true").lower() == "true":
            for row in sorted(rows, key=lambda r: r.get("score", 0), reverse=True)[:3]:
                self._attach_reddit_comments(row, token)
        return rows
    def x_twitter(self) -> list[dict[str, Any]]:
        if os.getenv("XQUIK_API_KEY"):
            return self._xquik_search()
        if os.getenv("PRODUCT_SCOUT_X_ADAPTER_COMMAND"):
            return self._external_x_adapter()
        if os.getenv("XAI_API_KEY"):
            return [item(
                "x_twitter",
                "XAI_API_KEY configured; adapter not enabled",
                "https://x.com/search",
                kind="adapter_notice",
                summary="xAI key is present, but this engine does not guess xAI's X-search contract. Set PRODUCT_SCOUT_X_ADAPTER_COMMAND or XQUIK_API_KEY for executable X search.",
                signals={"configured": "XAI_API_KEY"},
            )]
        if os.getenv("FROM_BROWSER") == "auto" or (os.getenv("AUTH_TOKEN") and os.getenv("CT0")):
            return [item(
                "x_twitter",
                "Browser-cookie X mode configured; adapter not enabled",
                "https://x.com/search",
                kind="adapter_notice",
                summary="Browser-cookie auth is present, but this conservative engine does not scrape x.com HTML. Set PRODUCT_SCOUT_X_ADAPTER_COMMAND to a consented local adapter such as Bird.",
                signals={"configured": "browser_or_manual_cookie"},
            )]
        return []
    def youtube(self) -> list[dict[str, Any]]:
        key = os.getenv("YOUTUBE_API_KEY")
        if not key or not self.query:
            return []
        published_after = dt.datetime.combine(self.start_date, dt.time.min, tzinfo=dt.timezone.utc).isoformat().replace("+00:00", "Z")
        published_before = dt.datetime.combine(self.end_date + dt.timedelta(days=1), dt.time.min, tzinfo=dt.timezone.utc).isoformat().replace("+00:00", "Z")
        params = urllib.parse.urlencode({
            "part": "snippet",
            "q": self.query,
            "type": "video",
            "order": "relevance",
            "publishedAfter": published_after,
            "publishedBefore": published_before,
            "maxResults": min(self.args.limit, 25),
            "key": key,
        })
        data = get_json(f"https://www.googleapis.com/youtube/v3/search?{params}", headers={"User-Agent": DEFAULT_UA})
        rows = []
        video_ids = []
        for video in data.get("items", []):
            vid = video.get("id", {}).get("videoId")
            if vid:
                video_ids.append(vid)
            snip = video.get("snippet", {})
            rows.append(item(
                "youtube",
                snip.get("title", ""),
                f"https://www.youtube.com/watch?v={vid}",
                kind="video",
                summary=snip.get("description", ""),
                published_at=snip.get("publishedAt", ""),
                score=25,
                signals={"channel": snip.get("channelTitle")},
                raw=video,
            ))
        stats = self._youtube_video_stats(video_ids, key)
        for row in rows:
            vid = row["url"].split("v=")[-1] if "v=" in row["url"] else ""
            if vid in stats:
                row["signals"].update(stats[vid])
                row["score"] = float(stats[vid].get("view_count") or 0) / 1000 + float(stats[vid].get("comment_count") or 0) * 2 + float(stats[vid].get("like_count") or 0) / 100
        if os.getenv("PRODUCT_SCOUT_YOUTUBE_COMMENTS", "false").lower() == "true":
            for row in sorted(rows, key=lambda r: r.get("score", 0), reverse=True)[:3]:
                self._attach_youtube_comments(row, key)
        return rows
    def _has_reddit_oauth(self) -> bool:
        return bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET"))

    def _reddit_token(self) -> str:
        client_id = os.environ["REDDIT_CLIENT_ID"]
        secret = os.environ["REDDIT_CLIENT_SECRET"]
        basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
        data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
        req = urllib.request.Request(
            "https://www.reddit.com/api/v1/access_token",
            data=data,
            headers={"Authorization": f"Basic {basic}", "User-Agent": os.getenv("REDDIT_USER_AGENT", DEFAULT_UA)},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["access_token"]

    def _reddit_public_low_rate(self) -> list[dict[str, Any]]:
        if not self.query:
            return []
        time.sleep(1.5)
        params = urllib.parse.urlencode({"q": self.query, "sort": "relevance", "t": "month", "limit": min(self.args.limit, 10)})
        data = get_json(f"https://www.reddit.com/search.json?{params}", headers={"User-Agent": os.getenv("REDDIT_USER_AGENT", DEFAULT_UA)})
        rows = []
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            rows.append(item("reddit_public", d.get("title", ""), "https://www.reddit.com" + d.get("permalink", ""), kind="discussion", score=float(d.get("score") or 0), signals={"comments": d.get("num_comments")}))
        return rows

    def _attach_reddit_comments(self, row: dict[str, Any], token: str) -> None:
        permalink = row.get("permalink")
        if not permalink:
            return
        url = f"https://oauth.reddit.com{permalink}.json?limit=5&sort=top"
        try:
            data = get_json(
                url,
                headers={"Authorization": f"Bearer {token}", "User-Agent": os.getenv("REDDIT_USER_AGENT", DEFAULT_UA)},
                timeout=20,
            )
        except Exception:
            return
        comments = []
        if isinstance(data, list) and len(data) > 1:
            for child in data[1].get("data", {}).get("children", [])[:5]:
                d = child.get("data", {})
                body = d.get("body")
                if body:
                    comments.append({"body": body[:500], "score": d.get("score"), "author": d.get("author")})
        if comments:
            row["signals"]["top_comments"] = comments

    def _has_x_config(self) -> bool:
        return bool(
            os.getenv("XAI_API_KEY")
            or os.getenv("XQUIK_API_KEY")
            or os.getenv("PRODUCT_SCOUT_X_ADAPTER_COMMAND")
            or os.getenv("FROM_BROWSER") == "auto"
            or (os.getenv("AUTH_TOKEN") and os.getenv("CT0"))
        )
    def _youtube_video_stats(self, video_ids: list[str], key: str) -> dict[str, dict[str, Any]]:
        if not video_ids:
            return {}
        params = urllib.parse.urlencode({"part": "statistics", "id": ",".join(video_ids[:50]), "key": key})
        try:
            data = get_json(f"https://www.googleapis.com/youtube/v3/videos?{params}", headers={"User-Agent": DEFAULT_UA})
        except Exception:
            return {}
        out: dict[str, dict[str, Any]] = {}
        for video in data.get("items", []):
            stats = video.get("statistics", {})
            out[video.get("id", "")] = {
                "view_count": self._safe_int(stats.get("viewCount")),
                "like_count": self._safe_int(stats.get("likeCount")),
                "comment_count": self._safe_int(stats.get("commentCount")),
            }
        return out

    def _attach_youtube_comments(self, row: dict[str, Any], key: str) -> None:
        if "v=" not in row.get("url", ""):
            return
        video_id = row["url"].split("v=")[-1]
        params = urllib.parse.urlencode({
            "part": "snippet",
            "videoId": video_id,
            "order": "relevance",
            "maxResults": 5,
            "textFormat": "plainText",
            "key": key,
        })
        try:
            data = get_json(f"https://www.googleapis.com/youtube/v3/commentThreads?{params}", headers={"User-Agent": DEFAULT_UA})
        except Exception:
            return
        comments = []
        for thread in data.get("items", []):
            snip = thread.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            text = snip.get("textDisplay")
            if text:
                comments.append({"text": text[:500], "likes": snip.get("likeCount"), "author": snip.get("authorDisplayName")})
        if comments:
            row["signals"]["top_comments"] = comments

    def _xquik_search(self) -> list[dict[str, Any]]:
        if not self.query:
            return []
        since = self.start_date.isoformat()
        until = (self.end_date + dt.timedelta(days=1)).isoformat()
        q = f"{self.query} since:{since} until:{until}"
        params = urllib.parse.urlencode({"q": q, "queryType": "Top", "limit": min(self.args.limit, 40)})
        data = get_json(
            f"https://xquik.com/api/v1/x/tweets/search?{params}",
            headers={"X-Api-Key": os.environ["XQUIK_API_KEY"], "User-Agent": DEFAULT_UA},
            timeout=30,
        )
        rows = []
        for idx, tweet in enumerate(data.get("tweets", []) if isinstance(data, dict) else []):
            author = tweet.get("author") or {}
            username = str(author.get("username") or "").lstrip("@")
            tweet_id = str(tweet.get("id") or "")
            url = f"https://x.com/{username}/status/{tweet_id}" if username and tweet_id else "https://x.com/search"
            text = str(tweet.get("text") or "").strip()
            likes = self._safe_int(tweet.get("likeCount"))
            reposts = self._safe_int(tweet.get("retweetCount"))
            replies = self._safe_int(tweet.get("replyCount"))
            quotes = self._safe_int(tweet.get("quoteCount"))
            views = self._safe_int(tweet.get("viewCount"))
            bookmarks = self._safe_int(tweet.get("bookmarkCount"))
            score_value = (likes or 0) + (reposts or 0) * 2 + (replies or 0) * 2 + (quotes or 0) * 2 + (bookmarks or 0) * 3
            rows.append(item(
                "xquik",
                text[:90] or f"Tweet {idx + 1}",
                url,
                kind="social_post",
                summary=text[:500],
                published_at=str(tweet.get("createdAt") or ""),
                score=float(score_value),
                signals={
                    "author": username,
                    "likes": likes,
                    "reposts": reposts,
                    "replies": replies,
                    "quotes": quotes,
                    "views": views,
                    "bookmarks": bookmarks,
                },
                raw=tweet,
            ))
        return rows

    def _external_x_adapter(self) -> list[dict[str, Any]]:
        command = os.environ["PRODUCT_SCOUT_X_ADAPTER_COMMAND"]
        payload = {
            "query": self.query,
            "days": self.days,
            "from_date": self.start_date.isoformat(),
            "to_date": self.end_date.isoformat(),
            "limit": self.args.limit,
        }
        completed = subprocess.run(
            command,
            input=json.dumps(payload),
            text=True,
            shell=True,
            capture_output=True,
            timeout=60,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"external X adapter failed: {completed.stderr.strip()[:300]}")
        data = json.loads(completed.stdout)
        raw_items = data.get("items", data if isinstance(data, list) else [])
        rows = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("text") or raw.get("summary") or raw.get("title") or "")
            rows.append(item(
                "x_external",
                str(raw.get("title") or text[:90] or "X result"),
                str(raw.get("url") or "https://x.com/search"),
                kind="social_post",
                summary=text[:500],
                published_at=str(raw.get("date") or raw.get("published_at") or ""),
                score=float(raw.get("score") or 0),
                signals=raw.get("signals") or raw.get("engagement") or {},
                raw=raw,
            ))
        return rows

