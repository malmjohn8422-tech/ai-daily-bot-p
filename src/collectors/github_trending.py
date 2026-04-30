import httpx
from bs4 import BeautifulSoup
from .base import Collector


class GitHubTrendingCollector(Collector):
    """GitHub Trending，直接抓取 github.com/trending 页面"""
    name = "github_trending"

    def fetch(self, params: dict | None = None) -> list[dict]:
        language = (params or {}).get("language", "")
        since = (params or {}).get("since", "daily")
        max_articles = (params or {}).get("max_articles", 10)

        url = "https://github.com/trending"
        if language:
            url += f"/{language}"
        url += f"?since={since}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        }

        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        results = []

        for article in soup.select("article.Box-row"):
            # 仓库名
            h2 = article.select_one("h2")
            if not h2:
                continue
            a = h2.select_one("a")
            if not a:
                continue
            full_name = a.get("href", "").strip("/")

            # 描述
            desc_elem = article.select_one("p.col-9")
            desc = desc_elem.get_text(strip=True) if desc_elem else ""

            # 编程语言
            lang_elem = article.select_one("[itemprop='programmingLanguage']")
            lang = lang_elem.get_text(strip=True) if lang_elem else ""

            # 星数
            stars_elem = article.select_one("a.Link--muted")
            stars = 0
            if stars_elem:
                stars_text = stars_elem.get_text(strip=True).replace(",", "")
                if stars_text.isdigit():
                    stars = int(stars_text)

            # Fork 数
            fork_elem = article.select_one("a.Link--muted ~ a.Link--muted")
            forks = 0
            if fork_elem:
                forks_text = fork_elem.get_text(strip=True).replace(",", "")
                if forks_text.isdigit():
                    forks = int(forks_text)

            results.append({
                "title": full_name,
                "url": f"https://github.com/{full_name}",
                "summary": desc,
                "source": "GitHub Trending",
                "extra": {
                    "stars": stars,
                    "forks": forks,
                    "language": lang,
                },
            })

            if len(results) >= max_articles:
                break

        return results
