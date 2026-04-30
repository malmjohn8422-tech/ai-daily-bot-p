from abc import ABC, abstractmethod


class Collector(ABC):
    """采集器基类——所有数据源的采集插件都继承此类"""

    name: str = ""

    @abstractmethod
    def fetch(self, params: dict | None = None) -> list[dict]:
        """采集数据，返回统一格式的列表。

        每条数据格式：
            {
                "title": str,          # 标题
                "url": str,            # 链接
                "summary": str,        # 摘要
                "source": str,         # 来源名称
                "extra": dict,         # 额外信息
            }
        """
        ...
