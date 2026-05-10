import os
import time

import httpx
from bs4 import BeautifulSoup
from .base import Collector
from ..logger import log


RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class GitHubTrendingCollector(Collector):
    """GitHub Trending，直接抓取 github.com/trending 页面"""
    name = "github_trending"

    def fetch(self, params: dict | None = None) -> list[dict]:
        language = (params or {}).get("language", "")
        since = (params or {}).get("since", "daily")
        max_articles = (params or {}).get("max_articles", 10)
        enrich_details = (params or {}).get("enrich_details", True)

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

        resp = self._get(url, headers)

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

            item = {
                "title": full_name,
                "url": f"https://github.com/{full_name}",
                "summary": desc,
                "source": "GitHub Trending",
                "extra": {
                    "stars": stars,
                    "forks": forks,
                    "language": lang,
                },
            }
            if enrich_details:
                self._enrich_repo_details(item)
            results.append(item)

            if len(results) >= max_articles:
                break

        if not results:
            log.warning(f"GitHub Trending 解析结果为空，页面结构可能变化: {url}")

        return results

    def _api_headers(self) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-daily-bot",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _enrich_repo_details(self, item: dict):
        full_name = item["title"]
        url = f"https://api.github.com/repos/{full_name}"
        try:
            resp = self._get(url, self._api_headers(), label=f"GitHub Repo API {full_name}")
            repo = resp.json()
        except Exception as e:
            log.warning(f"{full_name} 仓库详情获取失败，跳过增强信号: {e}")
            return

        extra = item.setdefault("extra", {})
        api_description = repo.get("description")
        if api_description and not item.get("summary"):
            item["summary"] = api_description
        extra.update({
            "repo_created_at": repo.get("created_at") or "",
            "repo_updated_at": repo.get("updated_at") or "",
            "repo_pushed_at": repo.get("pushed_at") or "",
            "open_issues": repo.get("open_issues_count") or 0,
            "watchers": repo.get("subscribers_count") or repo.get("watchers_count") or 0,
            "default_branch": repo.get("default_branch") or "",
            "archived": bool(repo.get("archived")),
            "disabled": bool(repo.get("disabled")),
            "license": (repo.get("license") or {}).get("spdx_id") or "",
            "topics": repo.get("topics") or [],
            "repo_api_enriched": True,
        })

    def _get(self, url: str, headers: dict, label: str = "GitHub Trending") -> httpx.Response:
        last_exc = None
        for attempt in range(1, 4):
            try:
                resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as e:
                last_exc = e
                status = e.response.status_code
                if attempt < 3 and status in RETRY_STATUS_CODES:
                    wait = 2 * (2 ** (attempt - 1))
                    log.warning(f"{label} HTTP {status}，第{attempt}次失败，{wait}s后重试")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"{label} 请求失败: HTTP {status} {url}") from e
            except httpx.RequestError as e:
                last_exc = e
                if attempt < 3:
                    wait = 2 * (2 ** (attempt - 1))
                    log.warning(f"{label} 网络错误，第{attempt}次失败: {e}，{wait}s后重试")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"{label} 网络请求失败: {e}") from e

        raise RuntimeError(f"{label} 请求失败: {last_exc}")
