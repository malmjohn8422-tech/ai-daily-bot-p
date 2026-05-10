import time

import httpx

from .base import Collector
from ..logger import log


RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class HackerNewsCollector(Collector):
    """Hacker News stories via the public Algolia API."""

    name = "hacker_news"

    def fetch(self, params: dict | None = None) -> list[dict]:
        params = params or {}
        query = params.get("query", "")
        max_articles = int(params.get("max_articles", 10))
        tags = params.get("tags", "story")

        api_params = {
            "tags": tags,
            "hitsPerPage": max_articles,
        }
        if query:
            api_params["query"] = query

        resp = self._get("https://hn.algolia.com/api/v1/search_by_date", params=api_params)
        payload = resp.json()
        hits = payload.get("hits") or []

        results = []
        for hit in hits[:max_articles]:
            title = hit.get("title") or hit.get("story_title") or ""
            url = hit.get("url") or hit.get("story_url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            if not title or not url:
                continue

            results.append({
                "title": title,
                "url": url,
                "summary": hit.get("story_text") or "",
                "source": "Hacker News",
                "extra": {
                    "score": hit.get("points") or 0,
                    "comments": hit.get("num_comments") or 0,
                    "author": hit.get("author") or "",
                    "created_at": hit.get("created_at") or "",
                    "hn_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                },
            })

        if not results:
            log.warning(f"Hacker News 采集结果为空: query={query!r}, tags={tags!r}")

        return results

    def _get(self, url: str, params: dict) -> httpx.Response:
        last_exc = None
        for attempt in range(1, 4):
            try:
                resp = httpx.get(url, params=params, timeout=15)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as e:
                last_exc = e
                status = e.response.status_code
                if attempt < 3 and status in RETRY_STATUS_CODES:
                    wait = 2 * (2 ** (attempt - 1))
                    log.warning(f"Hacker News HTTP {status}，第{attempt}次失败，{wait}s后重试")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Hacker News 请求失败: HTTP {status} {url}") from e
            except httpx.RequestError as e:
                last_exc = e
                if attempt < 3:
                    wait = 2 * (2 ** (attempt - 1))
                    log.warning(f"Hacker News 网络错误，第{attempt}次失败: {e}，{wait}s后重试")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Hacker News 网络请求失败: {e}") from e

        raise RuntimeError(f"Hacker News 请求失败: {last_exc}")
