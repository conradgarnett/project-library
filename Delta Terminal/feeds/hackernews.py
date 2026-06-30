"""HackerNews top stories feed — Firebase API, free, no auth."""
import asyncio
import aiohttp
import time
from dataclasses import dataclass, field
from typing import Optional

HN_BASE = "https://hacker-news.firebaseio.com/v0"


@dataclass
class HNState:
    stories: list = field(default_factory=list)
    updated: float = 0.0
    error:   Optional[str] = None


_state = HNState()


def get_hackernews():
    return _state


def _time_ago(ts: float) -> str:
    age = time.time() - ts
    if age < 60:
        return "just now"
    m = int(age // 60)
    if m < 60:
        return f"{m}m ago"
    h = int(age // 3600)
    if h < 24:
        return f"{h}h ago"
    return f"{int(h // 24)}d ago"


async def _fetch_item(session: aiohttp.ClientSession, item_id: int) -> Optional[dict]:
    try:
        async with session.get(
            f"{HN_BASE}/item/{item_id}.json",
            timeout=aiohttp.ClientTimeout(total=6),
        ) as r:
            if r.status == 200:
                return await r.json()
    except Exception:
        pass
    return None


async def run_poller(interval: int = 600):
    global _state
    async with aiohttp.ClientSession(
        headers={"User-Agent": "OpenBloombergTerminal/2.0"}
    ) as session:
        while True:
            try:
                async with session.get(
                    f"{HN_BASE}/topstories.json",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    ids = await r.json()

                top_ids = ids[:40]
                results = await asyncio.gather(*[_fetch_item(session, i) for i in top_ids])

                stories = []
                for item in results:
                    if not item or item.get("type") != "story" or not item.get("title"):
                        continue
                    url = item.get("url") or f"https://news.ycombinator.com/item?id={item['id']}"
                    try:
                        domain = url.split("://", 1)[1].split("/")[0].replace("www.", "")
                    except Exception:
                        domain = "news.ycombinator.com"
                    stories.append({
                        "id":       item["id"],
                        "title":    item.get("title", ""),
                        "url":      url,
                        "domain":   domain,
                        "score":    item.get("score", 0),
                        "comments": item.get("descendants", 0),
                        "author":   item.get("by", ""),
                        "time":     item.get("time", 0),
                        "time_ago": _time_ago(item.get("time", 0)),
                    })

                _state.stories = stories
                _state.updated = time.time()
                _state.error   = None

            except Exception as exc:
                _state.error = str(exc)

            await asyncio.sleep(interval)
