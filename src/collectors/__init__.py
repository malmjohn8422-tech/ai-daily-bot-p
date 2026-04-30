from .base import Collector
from .github_trending import GitHubTrendingCollector
from .none import NoneCollector

REGISTRY = {
    "github_trending": GitHubTrendingCollector,
    "none": NoneCollector,
}

def get_collector(name: str) -> type[Collector]:
    cls = REGISTRY.get(name)
    if not cls:
        raise KeyError(f"未知采集器: {name}，可选: {list(REGISTRY.keys())}")
    return cls
