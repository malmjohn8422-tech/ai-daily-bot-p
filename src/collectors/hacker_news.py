import httpx
from .base import Collector


class HackerNewsCollector(Collector):
    """Hacker News 热门，免费 API 无需认证"""
    name = "hacker_news"

    def fetch(self, params: dict | None = None) -> list[dict]:
        max_articles = (params or {}).get("max_articles", 10)

        # 获取当前最热 100 条
        resp = httpx.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=15,
        )
        resp.raise_for_status()
        ids = resp.json()[:max_articles]

        results = []
        for item_id in ids:
            item_resp = httpx.get(
                f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
                timeout=10,
            )
            if item_resp.status_code != 200:
                continue
            item = item_resp.json()
            if not item or item.get("type") != "story":
                continue

            title = item.get("title", "")
            url = item.get("url", f"https://news.ycombinator.com/item?id={item_id}")
            results.append({
                "title": title,
                "url": url,
                "summary": "",
                "source": "Hacker News",
                "extra": {
                    "score": item.get("score", 0),
                    "by": item.get("by", ""),
                    "comments": item.get("descendants", 0),
                },
            })

        return results
