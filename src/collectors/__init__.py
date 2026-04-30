from .base import Collector
from .hacker_news import HackerNewsCollector
from .github_trending import GitHubTrendingCollector

REGISTRY = {
    "hacker_news": HackerNewsCollector,
    "github_trending": GitHubTrendingCollector,
}

def get_collector(name: str) -> type[Collector]:
    cls = REGISTRY.get(name)
    if not cls:
        raise KeyError(f"未知采集器: {name}，可选: {list(REGISTRY.keys())}")
    return cls
