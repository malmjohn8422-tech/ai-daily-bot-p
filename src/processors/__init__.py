from .base import Processor
from .summarizer import SummarizerProcessor
from .weekly import WeeklySummarizerProcessor

REGISTRY = {
    "summarizer": SummarizerProcessor,
    "weekly": WeeklySummarizerProcessor,
}

def get_processor(name: str) -> type[Processor]:
    cls = REGISTRY.get(name)
    if not cls:
        raise KeyError(f"未知处理器: {name}，可选: {list(REGISTRY.keys())}")
    return cls
