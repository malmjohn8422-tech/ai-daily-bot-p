import time

import httpx

from .base import Collector
from ..logger import log


RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class HuggingFaceCollector(Collector):
    """Hugging Face Hub models, datasets, or spaces."""

    name = "hugging_face"

    ENDPOINTS = {
        "models": "https://huggingface.co/api/models",
        "datasets": "https://huggingface.co/api/datasets",
        "spaces": "https://huggingface.co/api/spaces",
    }

    def fetch(self, params: dict | None = None) -> list[dict]:
        params = params or {}
        repo_type = params.get("repo_type", "models")
        max_articles = int(params.get("max_articles", 10))
        url = self.ENDPOINTS.get(repo_type)
        if not url:
            raise ValueError(f"未知 Hugging Face repo_type: {repo_type}")

        api_params = {
            "limit": max_articles,
            "sort": params.get("sort", "downloads"),
            "direction": params.get("direction", "-1"),
            "full": "true",
        }
        for key in ("search", "filter", "author"):
            if params.get(key):
                api_params[key] = params[key]

        resp = self._get(url, api_params)
        payload = resp.json()
        if not isinstance(payload, list):
            raise RuntimeError("Hugging Face API 响应格式异常")

        results = []
        for repo in payload[:max_articles]:
            repo_id = repo.get("modelId") or repo.get("id") or ""
            if not repo_id:
                continue
            tags = repo.get("tags") or []
            results.append({
                "title": repo_id,
                "url": f"https://huggingface.co/{repo_id}",
                "summary": repo.get("pipeline_tag") or repo.get("library_name") or "",
                "source": f"Hugging Face {repo_type}",
                "extra": {
                    "repo_type": repo_type,
                    "downloads": repo.get("downloads") or 0,
                    "likes": repo.get("likes") or 0,
                    "tags": tags[:20] if isinstance(tags, list) else [],
                    "pipeline_tag": repo.get("pipeline_tag") or "",
                    "library_name": repo.get("library_name") or "",
                    "created_at": repo.get("createdAt") or "",
                    "last_modified": repo.get("lastModified") or "",
                },
            })

        if not results:
            log.warning(f"Hugging Face 采集结果为空: repo_type={repo_type!r}, params={api_params!r}")

        return results

    def _get(self, url: str, params: dict) -> httpx.Response:
        last_exc = None
        for attempt in range(1, 4):
            try:
                resp = httpx.get(url, params=params, timeout=20)
                resp.raise_for_status()
                return resp
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_exc = e
                status = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None
                if attempt < 3 and (status is None or status in RETRY_STATUS_CODES):
                    wait = 2 * (2 ** (attempt - 1))
                    log.warning(f"Hugging Face 请求失败，第{attempt}次: {e}，{wait}s后重试")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Hugging Face 请求失败: {e}") from e

        raise RuntimeError(f"Hugging Face 请求失败: {last_exc}")
