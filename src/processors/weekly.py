from datetime import datetime, timedelta
import zoneinfo

from .base import Processor
from ..storage import storage
from ..logger import log


class WeeklySummarizerProcessor(Processor):
    name = "weekly"

    @staticmethod
    def _metric_label(metric_name: str) -> str:
        return {
            "stars": "Stars",
            "score": "HN 分数",
            "comments": "评论数",
        }.get(metric_name, metric_name or "热度")

    def process(self, data: list[dict], ai_config: dict, params: dict | None = None) -> str:
        params = params or {}
        tz = zoneinfo.ZoneInfo("Asia/Shanghai")
        # Include today's daily report in the weekly summary. On the configured Sunday
        # run, this covers Monday through Sunday in Asia/Shanghai.
        report_end = datetime.now(tz).date() + timedelta(days=1)

        history = storage.get_trend_history(
            task_name=params.get("task_name", ""),
            days=7,
            end_date=report_end,
        )

        if not history:
            return "本周没有足够的历史数据。\n你需要先运行几天每日采集，下周日再来看看。"

        # 整理各天的数据
        date_sections = []
        all_items = {}
        for date in sorted(history.keys(), reverse=True):
            items = history[date]
            names = [item.get("title", "") for item in items]
            date_sections.append(f"{date}: {', '.join(names)}")
            for item in items:
                title = item.get("title", "")
                if title not in all_items:
                    all_items[title] = []
                metric_name = item.get("metric_name") or "stars"
                metric_value = item.get("metric_value")
                if metric_value in (None, 0) and metric_name == "stars":
                    metric_value = item.get("stars", 0)
                all_items[title].append({
                    "date": date,
                    "metric_name": metric_name,
                    "metric_value": metric_value or 0,
                    "rank": item.get("rank", 0),
                })

        # 计算每个项目本周出现次数和热度趋势
        item_summaries = []
        for title, appearances in all_items.items():
            appearances = sorted(appearances, key=lambda a: a["date"])
            metric_name = appearances[-1]["metric_name"]
            metric_label = self._metric_label(metric_name)
            first_value = appearances[0]["metric_value"]
            last_value = appearances[-1]["metric_value"]
            growth = last_value - first_value
            growth_text = f"+{growth}" if growth >= 0 else str(growth)
            item_summaries.append(
                f"  {title}: 出现{len(appearances)}天, {metric_label} {first_value}→{last_value}"
                f"({growth_text}), 最佳排名#{min(a['rank'] for a in appearances)}"
            )

        history_text = (
            "本周每日出现的项目:\n"
            + "\n".join(date_sections)
            + "\n\n本周各项目表现:\n"
            + "\n".join(item_summaries)
        )

        prompt = f"""你是一位资深技术编辑。请根据下面提供的一周 GitHub Trending 数据，撰写一份「一周趋势总结」。

要求：
1. 用中文输出
2. 分析本周整体趋势：本周热门方向是什么？哪些领域最活跃？
3. 列出本周最值得关注的 5 个项目，每个说明推荐理由和一句话要点
4. 标记「本周明星」「持续发热」「昙花一现」等标签
5. **识别明显异常的刷量项目（描述空洞但星级高、突然暴涨等）并标注「疑似刷量」，不要推荐**
6. 按项目分组展示而非按天展示
7. 末尾给出总结：下周值得关注的方向

一周数据：
{history_text}"""

        return self._call_ai(prompt, ai_config)

    def _call_ai(self, prompt: str, ai_config: dict) -> str:
        import httpx

        payload = {
            "model": ai_config.get("model", "gpt-4o"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }

        headers = {"Content-Type": "application/json"}
        if ai_config.get("api_key"):
            headers["Authorization"] = f"Bearer {ai_config['api_key']}"

        log.info(f"调用AI模型 (周报): {payload['model']}")
        resp = httpx.post(
            ai_config["api_base"],
            json=payload,
            headers=headers,
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()

        return result["choices"][0]["message"]["content"]
