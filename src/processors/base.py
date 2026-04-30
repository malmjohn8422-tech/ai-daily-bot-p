from abc import ABC, abstractmethod


class Processor(ABC):
    """处理器基类——所有 AI 处理插件都继承此类"""

    name: str = ""

    @abstractmethod
    def process(self, data: list[dict], ai_config: dict, params: dict | None = None) -> str:
        """处理采集到的数据，返回处理结果文本。"""
        ...
