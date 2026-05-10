from unittest.mock import patch

import httpx

from src.collectors.arxiv import ArxivCollector
from src.collectors.dev_to import DevToCollector
from src.collectors.github_trending import GitHubTrendingCollector
from src.collectors.hacker_news import HackerNewsCollector
from src.collectors.hugging_face import HuggingFaceCollector
from src.collectors.product_hunt import ProductHuntCollector


def _response(status_code: int, text: str = "", json_data: dict | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://github.com/trending?since=daily")
    if json_data is not None:
        return httpx.Response(status_code, json=json_data, request=request)
    return httpx.Response(status_code, text=text, request=request)


def test_github_trending_retries_retryable_http_status():
    html = """
    <article class="Box-row">
      <h2><a href="/owner/repo">owner / repo</a></h2>
      <p class="col-9">desc</p>
      <span itemprop="programmingLanguage">Python</span>
      <a class="Link--muted">1,234</a>
      <a class="Link--muted">56</a>
    </article>
    """

    with patch("src.collectors.github_trending.time.sleep") as sleep, patch("src.collectors.github_trending.httpx.get") as get:
        get.side_effect = [
            _response(429),
            _response(200, html),
            _response(200, json_data={"description": "api desc", "topics": []}),
        ]

        result = GitHubTrendingCollector().fetch({"max_articles": 1})

    assert result[0]["title"] == "owner/repo"
    assert result[0]["extra"]["stars"] == 1234
    sleep.assert_called_once_with(2)


def test_github_trending_enriches_repo_details():
    html = """
    <article class="Box-row">
      <h2><a href="/owner/repo">owner / repo</a></h2>
      <p class="col-9"></p>
      <a class="Link--muted">1,000</a>
      <a class="Link--muted">100</a>
    </article>
    """
    api_payload = {
        "description": "api desc",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-05-01T00:00:00Z",
        "pushed_at": "2026-05-02T00:00:00Z",
        "open_issues_count": 12,
        "subscribers_count": 34,
        "default_branch": "main",
        "archived": False,
        "disabled": False,
        "license": {"spdx_id": "MIT"},
        "topics": ["ai", "daily"],
    }

    with patch("src.collectors.github_trending.httpx.get") as get:
        get.side_effect = [_response(200, html), _response(200, json_data=api_payload)]

        result = GitHubTrendingCollector().fetch({"max_articles": 1})

    item = result[0]
    assert item["summary"] == "api desc"
    assert item["extra"]["repo_api_enriched"] is True
    assert item["extra"]["open_issues"] == 12
    assert item["extra"]["watchers"] == 34
    assert item["extra"]["license"] == "MIT"
    assert item["extra"]["topics"] == ["ai", "daily"]


def test_hacker_news_collector_parses_hits():
    payload = {
        "hits": [
            {
                "title": "AI agent framework",
                "url": "https://example.com/agent",
                "points": 42,
                "num_comments": 7,
                "author": "pg",
                "created_at": "2026-05-01T00:00:00Z",
                "objectID": "123",
            }
        ]
    }

    with patch("src.collectors.hacker_news.httpx.get") as get:
        get.return_value = _response(200, json_data=payload)

        result = HackerNewsCollector().fetch({"query": "ai", "max_articles": 1})

    assert result[0]["title"] == "AI agent framework"
    assert result[0]["source"] == "Hacker News"
    assert result[0]["extra"]["score"] == 42
    assert result[0]["extra"]["comments"] == 7


def test_arxiv_collector_parses_atom_entries():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>https://arxiv.org/abs/2601.00001</id>
        <title>Agent Paper</title>
        <summary> A useful paper. </summary>
        <published>2026-01-01T00:00:00Z</published>
        <updated>2026-01-02T00:00:00Z</updated>
        <author><name>Alice</name></author>
        <category term="cs.AI"/>
        <link title="pdf" href="https://arxiv.org/pdf/2601.00001"/>
      </entry>
    </feed>"""

    with patch("src.collectors.arxiv.httpx.get") as get:
        get.return_value = _response(200, text=xml)

        result = ArxivCollector().fetch({"query": "cat:cs.AI", "max_articles": 1})

    assert result[0]["title"] == "Agent Paper"
    assert result[0]["source"] == "arXiv"
    assert result[0]["extra"]["authors"] == ["Alice"]
    assert result[0]["extra"]["categories"] == ["cs.AI"]


def test_hugging_face_collector_parses_models():
    payload = [
        {
            "modelId": "org/model",
            "downloads": 123,
            "likes": 45,
            "tags": ["text-generation"],
            "pipeline_tag": "text-generation",
            "createdAt": "2026-01-01T00:00:00Z",
            "lastModified": "2026-05-01T00:00:00Z",
        }
    ]

    with patch("src.collectors.hugging_face.httpx.get") as get:
        get.return_value = _response(200, json_data=payload)

        result = HuggingFaceCollector().fetch({"repo_type": "models", "max_articles": 1})

    assert result[0]["title"] == "org/model"
    assert result[0]["extra"]["downloads"] == 123
    assert result[0]["extra"]["likes"] == 45


def test_product_hunt_collector_skips_without_token(monkeypatch):
    monkeypatch.delenv("PRODUCT_HUNT_TOKEN", raising=False)

    assert ProductHuntCollector().fetch({"max_articles": 1}) == []


def test_product_hunt_collector_parses_posts(monkeypatch):
    monkeypatch.setenv("PRODUCT_HUNT_TOKEN", "token")
    payload = {
        "data": {
            "posts": {
                "edges": [
                    {
                        "node": {
                            "id": "1",
                            "name": "Agent Tool",
                            "tagline": "Build agents",
                            "url": "https://producthunt.com/posts/agent-tool",
                            "votesCount": 100,
                            "commentsCount": 5,
                            "createdAt": "2026-05-01T00:00:00Z",
                            "website": "https://example.com",
                        }
                    }
                ]
            }
        }
    }

    with patch("src.collectors.product_hunt.httpx.post") as post:
        post.return_value = _response(200, json_data=payload)

        result = ProductHuntCollector().fetch({"max_articles": 1})

    assert result[0]["title"] == "Agent Tool"
    assert result[0]["extra"]["votes"] == 100
    assert result[0]["extra"]["website"] == "https://example.com"


def test_dev_to_collector_parses_articles():
    payload = [
        {
            "title": "Python AI",
            "url": "https://dev.to/a/python-ai",
            "description": "Guide",
            "tag_list": ["python", "ai"],
            "public_reactions_count": 12,
            "comments_count": 3,
            "reading_time_minutes": 4,
            "published_at": "2026-05-01T00:00:00Z",
            "user": {"username": "alice"},
        }
    ]

    with patch("src.collectors.dev_to.httpx.get") as get:
        get.return_value = _response(200, json_data=payload)

        result = DevToCollector().fetch({"tag": "ai", "max_articles": 1})

    assert result[0]["title"] == "Python AI"
    assert result[0]["extra"]["tags"] == ["python", "ai"]
    assert result[0]["extra"]["reactions"] == 12
