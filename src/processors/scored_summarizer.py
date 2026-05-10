from .base import Processor
from .summarizer import SummarizerProcessor
from ..ai_client import call_chat_completion


class ScoredSummarizerProcessor(Processor):
    """Personalized daily brief with AI scoring and filtering."""

    name = "scored_summarizer"

    @staticmethod
    def _preferences_text(params: dict) -> str:
        prefs = params.get("preferences") or {}
        interests = prefs.get("interests") or []
        exclude = prefs.get("exclude") or []
        min_score = prefs.get("min_score", 7)

        return (
            f"最低推荐分: {min_score}/10\n"
            f"优先关注: {', '.join(interests) if interests else '未设置'}\n"
            f"尽量过滤: {', '.join(exclude) if exclude else '未设置'}"
        )

    @staticmethod
    def _trim_text(text: str, limit: int = 700) -> str:
        text = " ".join((text or "").split())
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    def _format_item(self, item: dict, index: int) -> str:
        trimmed = dict(item)
        trimmed["summary"] = self._trim_text(item.get("summary", ""))
        return SummarizerProcessor._format_item(trimmed, index)

    def process(self, data: list[dict], ai_config: dict, params: dict | None = None) -> str:
        params = params or {}
        if not data:
            return "今天没有新内容。"

        max_items = int(params.get("max_items", 40))
        data = data[:max_items]
        items_text = "\n\n".join(
            self._format_item(item, i + 1)
            for i, item in enumerate(data)
        )
        preferences = self._preferences_text(params)

        prompt = f"""你是一个技术信息雷达编辑。请先根据用户偏好给每条内容打分，再输出一份中文每日简报。

用户偏好：
{preferences}

评分要求：
1. 给每条内容打 0-10 分，分数要体现质量、热度、讨论度、技术/产品价值、可信度、时效性和可行动性。
2. 题材不限；不要因为内容不是 AI、LLM 或开发工具就天然降分。只要质量高、有热度、讨论多、值得了解，就应正常推荐。
3. 在质量相近时，AI/LLM 应用、开发者工具、自动化、agents、开源基础设施相关内容应获得更高权重。
4. 明显偏离用户排除项、营销味重、重复度高、缺乏有效信息的内容应低分；NFT 相关内容默认过滤，除非它是重要安全事件、基础设施漏洞或行业级技术分析。
5. 不要只因为 Stars、HN 分数、点赞或评论数高就高分；必须结合项目/文章/产品本身价值。
6. 输出主体只展开推荐分达到最低分的内容；未达到最低分的内容放入「已过滤」一行，简短列出标题、分数和一句过滤原因。
7. 每个保留项必须包含：标题、链接、来源、推荐分、推荐理由、适合关注的人。
8. 对 GitHub 项目的疑似刷量判断要保守：只有多项异常证据同时出现才标注「疑似刷量」；证据不足时按正常项目评价。
9. 最后给出今日最值得投入时间看的 3 项。

原始内容：
{items_text}"""

        content = call_chat_completion(prompt, ai_config, purpose="个性化日报")
        sources = sorted({item.get("source", "") for item in data if item.get("source")})
        return f"📡 数据来源: {'、'.join(sources)}\n\n{content}"
