import time

import httpx

from .base import Collector
from ..logger import log


RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class DevToCollector(Collector):
    """DEV Community articles via the Forem API."""

    name = "dev_to"

    def fetch(self, params: dict | None = None) -> list[dict]:
        params = params or {}
        max_articles = int(params.get("max_articles", 10))
        api_params = {
            "per_page": max_articles,
            "page": int(params.get("page", 1)),
        }
        for key in ("tag", "tags", "username", "state", "top"):
            if params.get(key):
                api_params[key] = params[key]

        resp = self._get("https://dev.to/api/articles", api_params)
        payload = resp.json()
        if not isinstance(payload, list):
            raise RuntimeError("Dev.to API 响应格式异常")

        results = []
        for article in payload[:max_articles]:
            title = article.get("title") or ""
            url = article.get("url") or ""
            if not title or not url:
                continue
            user = article.get("user") or {}
            results.append({
                "title": title,
                "url": url,
                "summary": article.get("description") or "",
                "source": "Dev.to",
                "extra": {
                    "tags": article.get("tag_list") or [],
                    "reactions": article.get("public_reactions_count") or 0,
                    "comments": article.get("comments_count") or 0,
                    "reading_time_minutes": article.get("reading_time_minutes") or 0,
                    "published_at": article.get("published_at") or "",
                    "author": user.get("username") or "",
                },
            })

        if not results:
            log.warning(f"Dev.to 采集结果为空: params={api_params!r}")

        return results

    def _get(self, url: str, params: dict) -> httpx.Response:
        headers = {"User-Agent": "ai-daily-bot"}
        last_exc = None
        for attempt in range(1, 4):
            try:
                resp = httpx.get(url, params=params, headers=headers, timeout=15)
                resp.raise_for_status()
                return resp
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_exc = e
                status = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None
                if attempt < 3 and (status is None or status in RETRY_STATUS_CODES):
                    wait = 2 * (2 ** (attempt - 1))
                    log.warning(f"Dev.to 请求失败，第{attempt}次: {e}，{wait}s后重试")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Dev.to 请求失败: {e}") from e

        raise RuntimeError(f"Dev.to 请求失败: {last_exc}")
