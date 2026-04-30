from abc import ABC, abstractmethod


class NotificationPartialFailure(RuntimeError):
    """Raised when a notification was only partly delivered."""


class Notifier(ABC):
    """通知器基类——所有推送插件都继承此类"""

    name: str = ""

    @abstractmethod
    def send(self, title: str, content: str, config: dict) -> bool:
        """推送消息，返回是否成功。"""
        ...
