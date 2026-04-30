from .base import Notifier
from .telegram import TelegramNotifier
from .email import EmailNotifier

REGISTRY = {
    "telegram": TelegramNotifier,
    "email": EmailNotifier,
}

def get_notifier(name: str) -> type[Notifier]:
    cls = REGISTRY.get(name)
    if not cls:
        raise KeyError(f"未知通知器: {name}，可选: {list(REGISTRY.keys())}")
    return cls
