import time
import xml.etree.ElementTree as ET

import httpx

from .base import Collector
from ..logger import log


RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


class ArxivCollector(Collector):
    """arXiv papers via the official Atom API."""

    name = "arxiv"

    def fetch(self, params: dict | None = None) -> list[dict]:
        params = params or {}
        query = params.get("query", "cat:cs.AI OR cat:cs.CL OR cat:cs.LG")
        max_articles = int(params.get("max_articles", 10))

        resp = self._get(
            "https://export.arxiv.org/api/query",
            {
                "search_query": query,
                "start": 0,
                "max_results": max_articles,
                "sortBy": params.get("sort_by", "submittedDate"),
                "sortOrder": params.get("sort_order", "descending"),
            },
        )
        root = ET.fromstring(resp.text)
        results = []

        for entry in root.findall("atom:entry", ATOM_NS):
            title = self._text(entry, "atom:title")
            summary = self._text(entry, "atom:summary")
            url = self._text(entry, "atom:id")
            authors = [
                self._text(author, "atom:name")
                for author in entry.findall("atom:author", ATOM_NS)
            ]
            categories = [
                category.attrib.get("term", "")
                for category in entry.findall("atom:category", ATOM_NS)
                if category.attrib.get("term")
            ]

            results.append({
                "title": title,
                "url": url,
                "summary": " ".join(summary.split()),
                "source": "arXiv",
                "extra": {
                    "authors": authors,
                    "categories": categories,
                    "published_at": self._text(entry, "atom:published"),
                    "updated_at": self._text(entry, "atom:updated"),
                    "pdf_url": self._pdf_url(entry),
                },
            })

        if not results:
            log.warning(f"arXiv 采集结果为空: query={query!r}")

        return results

    @staticmethod
    def _text(elem: ET.Element, path: str) -> str:
        found = elem.find(path, ATOM_NS)
        return found.text.strip() if found is not None and found.text else ""

    @staticmethod
    def _pdf_url(entry: ET.Element) -> str:
        for link in entry.findall("atom:link", ATOM_NS):
            if link.attrib.get("title") == "pdf":
                return link.attrib.get("href", "")
        return ""

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
                    log.warning(f"arXiv 请求失败，第{attempt}次: {e}，{wait}s后重试")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"arXiv 请求失败: {e}") from e

        raise RuntimeError(f"arXiv 请求失败: {last_exc}")
