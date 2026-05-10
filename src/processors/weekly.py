from datetime import datetime, timedelta
import json
import zoneinfo

from .base import Processor
from ..ai_client import call_chat_completion
from ..storage import storage


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

        history = self._load_history(params, report_end)

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
                    "url": item.get("url", ""),
                    "language": item.get("language", ""),
                    "stars": item.get("stars", 0),
                    "forks": item.get("forks", 0),
                    "watchers": item.get("watchers", 0),
                    "open_issues": item.get("open_issues", 0),
                    "repo_created_at": item.get("repo_created_at", ""),
                    "repo_pushed_at": item.get("repo_pushed_at", ""),
                    "license": item.get("license", ""),
                    "topics": item.get("topics", ""),
                    "archived": item.get("archived", 0),
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
            latest = appearances[-1]
            stars = latest.get("stars", 0) or 0
            forks = latest.get("forks", 0) or 0
            fork_ratio = f"{forks / stars:.3f}" if stars else "未知"
            topics = latest.get("topics") or ""
            if isinstance(topics, str):
                try:
                    topics = json.loads(topics)
                except json.JSONDecodeError:
                    topics = []
            topics_text = ", ".join(topics[:8]) if isinstance(topics, list) and topics else "无"
            growth = last_value - first_value
            growth_text = f"+{growth}" if growth >= 0 else str(growth)
            item_summaries.append(
                f"  {title}: 出现{len(appearances)}天, {metric_label} {first_value}→{last_value}"
                f"({growth_text}), 最佳排名#{min(a['rank'] for a in appearances)}, "
                f"Stars {stars}, Forks {forks}, Fork/Star {fork_ratio}, "
                f"Watchers {latest.get('watchers', 0)}, Open issues {latest.get('open_issues', 0)}, "
                f"创建 {latest.get('repo_created_at') or '未知'}, 最近提交 {latest.get('repo_pushed_at') or '未知'}, "
                f"License {latest.get('license') or '未知'}, Topics {topics_text}, "
                f"Archived {bool(latest.get('archived'))}, 语言 {latest.get('language') or '未知'}, "
                f"链接 {latest.get('url') or '无'}"
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
5. 疑似刷量判断要保守，并优先识别正常优质项目：项目有清晰用途、近期仍有提交、topics/license/issue/watchers 等社区信号合理时，即使 Stars 高、简介短或增长快，也应按正常项目评价。
6. 不要因为项目新、Stars 高、简介短、单周增长快、或 Fork/Star 比例单项异常就下结论。只有同时出现多项明确异常信号时，才可标注「疑似刷量」，例如：
   - 项目用途/技术价值缺乏清晰支撑
   - Stars 很高但 Forks 极低，且 Fork/Star 比例明显不符合该类项目常识
   - 多日趋势呈现无法解释的异常暴涨
   - 长期无提交/归档/禁用，且社区信号与热度明显不匹配
   - 社区信号与项目价值明显不匹配
   证据不足时不要标注「疑似刷量」，按正常项目评价即可。
7. 不要把「疑似刷量」作为降低评分的唯一理由；如果项目本身有明确价值，应正常推荐。
8. 按项目分组展示而非按天展示
9. 末尾给出总结：下周值得关注的方向

一周数据：
{history_text}"""

        return self._call_ai(prompt, ai_config)

    def _call_ai(self, prompt: str, ai_config: dict) -> str:
        return call_chat_completion(prompt, ai_config, purpose="周报")

    @staticmethod
    def _merge_history(base: dict[str, list[dict]], extra: dict[str, list[dict]]) -> dict[str, list[dict]]:
        for date_key, items in extra.items():
            existing = base.setdefault(date_key, [])
            seen = {(item.get("title"), item.get("url")) for item in existing}
            for item in items:
                key = (item.get("title"), item.get("url"))
                if key not in seen:
                    existing.append(item)
                    seen.add(key)
        return base

    def _load_history(self, params: dict, report_end) -> dict[str, list[dict]]:
        task_names = [params.get("task_name", "")]
        task_names.extend(params.get("history_aliases") or [])

        merged: dict[str, list[dict]] = {}
        for task_name in task_names:
            if not task_name:
                continue
            history = storage.get_trend_history(
                task_name=task_name,
                days=7,
                end_date=report_end,
            )
            self._merge_history(merged, history)
        return merged
