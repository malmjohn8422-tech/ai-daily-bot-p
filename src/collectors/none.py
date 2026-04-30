from .base import Collector


class NoneCollector(Collector):
    """No-op collector for tasks that only process existing local data."""

    name = "none"

    def fetch(self, params: dict | None = None) -> list[dict]:
        return []
