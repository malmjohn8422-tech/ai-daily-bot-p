from datetime import datetime
import zoneinfo

from .base import Processor
from ..storage import storage
from ..logger import log
from ..retry import retry


class WeeklySummarizerProcessor(Processor):
    name = "weekly"

    def process(self, data: list[dict], ai_config: dict, params: dict | None = None) -> str:
        tz = zoneinfo.ZoneInfo("Asia/Shanghai")
        today = datetime.now(tz)
        weekday = today.weekday()
        days_to_sunday = (weekday + 1) % 7
        sunday = today.replace(hour=0, minute=0, second=0, microsecond=0)
        if days_to_sunday > 0:
            from datetime import timedelta
            sunday -= timedelta(days=days_to_sunday)

        history = storage.get_trend_history(
            task_name=params.get("task_name", ""),
            days=7,
            end_date=sunday,
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
                all_items[title].append({
                    "date": date,
                    "stars": item.get("stars", 0),
                    "rank": item.get("rank", 0),
                })

        # 计算每个项目本周出现次数和星数趋势
        item_summaries = []
        for title, appearances in all_items.items():
            dates = sorted([a["date"] for a in appearances])
            stars = [a["stars"] for a in appearances]
            first_stars = stars[0]
            last_stars = stars[-1]
            growth = last_stars - first_stars
            item_summaries.append(
                f"  {title}: 出现{len(appearances)}天, Stars {first_stars}→{last_stars}"
                f"(+{growth}), 最佳排名#{min(a['rank'] for a in appearances)}"
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

    @retry(max_attempts=3, delay=2, backoff=2)
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
