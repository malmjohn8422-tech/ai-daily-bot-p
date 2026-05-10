from .base import Collector
from .arxiv import ArxivCollector
from .dev_to import DevToCollector
from .github_trending import GitHubTrendingCollector
from .hacker_news import HackerNewsCollector
from .hugging_face import HuggingFaceCollector
from .none import NoneCollector
from .product_hunt import ProductHuntCollector

REGISTRY = {
    "arxiv": ArxivCollector,
    "dev_to": DevToCollector,
    "github_trending": GitHubTrendingCollector,
    "hacker_news": HackerNewsCollector,
    "hugging_face": HuggingFaceCollector,
    "none": NoneCollector,
    "product_hunt": ProductHuntCollector,
}

def get_collector(name: str) -> type[Collector]:
    cls = REGISTRY.get(name)
    if not cls:
        raise KeyError(f"未知采集器: {name}，可选: {list(REGISTRY.keys())}")
    return cls
