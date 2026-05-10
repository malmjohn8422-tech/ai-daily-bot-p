import os
import time

import httpx

from .base import Collector
from ..logger import log


RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class ProductHuntCollector(Collector):
    """Product Hunt posts via API v2 GraphQL."""

    name = "product_hunt"

    QUERY = """
    query Posts($first: Int!) {
      posts(first: $first) {
        edges {
          node {
            id
            name
            tagline
            url
            votesCount
            commentsCount
            createdAt
            website
          }
        }
      }
    }
    """

    def fetch(self, params: dict | None = None) -> list[dict]:
        params = params or {}
        token = os.environ.get("PRODUCT_HUNT_TOKEN")
        if not token:
            log.warning("未设置 PRODUCT_HUNT_TOKEN，跳过 Product Hunt 采集")
            return []

        max_articles = int(params.get("max_articles", 10))
        resp = self._post(
            {"query": self.QUERY, "variables": {"first": max_articles}},
            token,
        )
        payload = resp.json()
        if payload.get("errors"):
            raise RuntimeError(f"Product Hunt API 返回错误: {payload['errors']}")

        edges = (((payload.get("data") or {}).get("posts") or {}).get("edges") or [])
        results = []
        for edge in edges[:max_articles]:
            node = edge.get("node") or {}
            name = node.get("name") or ""
            if not name:
                continue
            results.append({
                "title": name,
                "url": node.get("url") or node.get("website") or "",
                "summary": node.get("tagline") or "",
                "source": "Product Hunt",
                "extra": {
                    "votes": node.get("votesCount") or 0,
                    "comments": node.get("commentsCount") or 0,
                    "created_at": node.get("createdAt") or "",
                    "website": node.get("website") or "",
                    "product_hunt_id": node.get("id") or "",
                },
            })

        if not results:
            log.warning("Product Hunt 采集结果为空")

        return results

    def _post(self, payload: dict, token: str) -> httpx.Response:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        last_exc = None
        for attempt in range(1, 4):
            try:
                resp = httpx.post(
                    "https://api.producthunt.com/v2/api/graphql",
                    json=payload,
                    headers=headers,
                    timeout=20,
                )
                resp.raise_for_status()
                return resp
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_exc = e
                status = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None
                if attempt < 3 and (status is None or status in RETRY_STATUS_CODES):
                    wait = 2 * (2 ** (attempt - 1))
                    log.warning(f"Product Hunt 请求失败，第{attempt}次: {e}，{wait}s后重试")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Product Hunt 请求失败: {e}") from e

        raise RuntimeError(f"Product Hunt 请求失败: {last_exc}")
