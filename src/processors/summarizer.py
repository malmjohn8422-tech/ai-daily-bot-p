import httpx
from .base import Processor
from ..logger import log
from ..retry import retry


class SummarizerProcessor(Processor):
    name = "summarizer"

    @staticmethod
    def _format_trend_metric(item: dict) -> str:
        metric_name = item.get("metric_name") or "stars"
        metric_value = item.get("metric_value")
        if metric_value in (None, 0) and metric_name == "stars":
            metric_value = item.get("stars", 0)

        labels = {
            "stars": "Stars",
            "score": "HN 分数",
            "comments": "评论数",
        }
        label = labels.get(metric_name, metric_name or "热度")
        return f"{label}: {metric_value}" if metric_value else f"排名: {item.get('rank', '-')}"

    def process(self, data: list[dict], ai_config: dict, params: dict | None = None) -> str:
        if not data:
            return "今天没有新内容。"

        items_text = "\n\n".join(
            f"【{i+1}】{item['title']}\n链接: {item['url']}\n简介: {item['summary']}"
            for i, item in enumerate(data)
        )

        trend = (params or {}).get("_trend_history")
        trend_section = ""
        trend_requirement = "6. 如果没有趋势历史数据，不要编造「连续在榜」「星级猛增」等趋势标签。"
        if trend:
            trend_lines = ["## 近期趋势历史"]
            for date in sorted(trend.keys(), reverse=True):
                titles = [
                    f"  {item.get('title', '')} ({self._format_trend_metric(item)})"
                    for item in trend[date]
                ]
                trend_lines.append(f"{date}:\n" + "\n".join(titles))
            trend_section = "\n\n" + "\n".join(trend_lines)
            trend_requirement = """6. 根据趋势历史分析今日项目相比历史的变化：
   - 标出「新上榜」「连续 X 天在榜」「热度猛增」等标签
   - 对持续多日上榜的项目说明热度变化趋势
   - 在今日小结中增加一段趋势解读"""

        prompt = f"""你是一个信息简报编辑。请将以下内容整理成一份每日简报。

要求：
1. 用中文输出
2. **严格按原始顺序排列，不要重新排序**
3. 每个项目保留原标题和链接，用一句话概括亮点
4. 在每个项目后面加上你的推荐星数，格式：★★★★★（5星）
   - ★★★★★ = 必看项目
   - ★★★★☆ = 推荐项目
   - ★★★☆☆ = 可看可不看
   - ★★☆☆☆ = 有亮点但没什么看的必要
   - ★☆☆☆☆ = 不推荐
5. 末尾给出今日小结
{trend_requirement}{trend_section}

原始内容：
{items_text}"""

        return self._call_ai(prompt, ai_config, data)

    @retry(max_attempts=3, delay=2, backoff=2)
    def _call_ai(self, prompt: str, ai_config: dict, data: list[dict]) -> str:
        payload = {
            "model": ai_config.get("model", "gpt-4o"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }

        headers = {"Content-Type": "application/json"}
        if ai_config.get("api_key"):
            headers["Authorization"] = f"Bearer {ai_config['api_key']}"

        log.info(f"调用AI模型: {payload['model']}")
        resp = httpx.post(
            ai_config["api_base"],
            json=payload,
            headers=headers,
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()

        content = result["choices"][0]["message"]["content"]
        sources = set(item["source"] for item in data if item.get("source"))
        source_str = "、".join(sources)
        return f"📡 数据来源: {source_str}\n\n{content}"
