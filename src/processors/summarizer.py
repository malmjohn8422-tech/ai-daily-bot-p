from .base import Processor
from ..ai_client import call_chat_completion


class SummarizerProcessor(Processor):
    name = "summarizer"

    @staticmethod
    def _format_item(item: dict, index: int) -> str:
        extra = item.get("extra") or {}
        stars = extra.get("stars", 0) or 0
        forks = extra.get("forks", 0) or 0
        language = extra.get("language", "") or "未知"
        fork_ratio = f"{forks / stars:.3f}" if stars else "未知"
        topics = extra.get("topics") or []
        topics_text = ", ".join(topics[:8]) if isinstance(topics, list) and topics else "无"
        tags = extra.get("tags") or []
        tags_text = ", ".join(tags[:10]) if isinstance(tags, list) and tags else "无"
        authors = extra.get("authors") or []
        authors_text = ", ".join(authors[:5]) if isinstance(authors, list) and authors else extra.get("author", "无")
        categories = extra.get("categories") or []
        categories_text = ", ".join(categories[:8]) if isinstance(categories, list) and categories else "无"
        return (
            f"【{index}】{item['title']}\n"
            f"链接: {item['url']}\n"
            f"来源: {item.get('source') or '未知'}\n"
            f"简介: {item['summary'] or '无'}\n"
            f"作者: {authors_text}\n"
            f"发布时间: {extra.get('published_at') or extra.get('created_at') or '未知'}\n"
            f"语言: {language}\n"
            f"Stars: {stars}\n"
            f"Forks: {forks}\n"
            f"Fork/Star 比例: {fork_ratio}\n"
            f"HN 分数: {extra.get('score', 0)}\n"
            f"HN 评论数: {extra.get('comments', 0)}\n"
            f"投票/点赞: {extra.get('votes', 0) or extra.get('likes', 0)}\n"
            f"下载量: {extra.get('downloads', 0)}\n"
            f"反应数: {extra.get('reactions', 0)}\n"
            f"阅读时间: {extra.get('reading_time_minutes', 0)} 分钟\n"
            f"Watchers: {extra.get('watchers', 0)}\n"
            f"Open issues: {extra.get('open_issues', 0)}\n"
            f"创建时间: {extra.get('repo_created_at') or '未知'}\n"
            f"最近提交: {extra.get('repo_pushed_at') or '未知'}\n"
            f"最近更新: {extra.get('repo_updated_at') or '未知'}\n"
            f"License: {extra.get('license') or '未知'}\n"
            f"Topics: {topics_text}\n"
            f"Tags: {tags_text}\n"
            f"分类: {categories_text}\n"
            f"Pipeline: {extra.get('pipeline_tag') or '未知'}\n"
            f"PDF: {extra.get('pdf_url') or '无'}\n"
            f"官网: {extra.get('website') or '无'}\n"
            f"Archived: {extra.get('archived', False)}"
        )

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

        items_text = "\n\n".join(self._format_item(item, i + 1) for i, item in enumerate(data))

        trend = (params or {}).get("_trend_history")
        trend_section = ""
        trend_requirement = "9. 如果没有趋势历史数据，不要编造「连续在榜」「星级猛增」等趋势标签。"
        if trend:
            trend_lines = ["## 近期趋势历史"]
            for date in sorted(trend.keys(), reverse=True):
                titles = [
                    f"  {item.get('title', '')} ({self._format_trend_metric(item)})"
                    for item in trend[date]
                ]
                trend_lines.append(f"{date}:\n" + "\n".join(titles))
            trend_section = "\n\n" + "\n".join(trend_lines)
            trend_requirement = """9. 根据趋势历史分析今日项目相比历史的变化：
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
5. 疑似刷量判断要保守，并优先识别正常优质项目：项目有清晰用途、近期仍有提交、topics/license/issue/watchers 等社区信号合理时，即使 Stars 高或简介短，也应按正常项目评价。
6. 不要因为项目新、Stars 高、简介短、增长快、或 Fork/Star 比例单项异常就下结论。只有同时出现多项明确异常信号时，才可标注「疑似刷量」，例如：
   - 简介非常空洞或与项目用途明显不符
   - Stars 很高但 Forks 极低，且 Fork/Star 比例明显不符合该类项目常识
   - 结合趋势历史出现无法解释的异常暴涨
   - 长期无提交/归档/禁用，且社区信号与热度明显不匹配
   - 项目价值、技术方向、维护活跃度和社区信号都缺乏支撑
   证据不足时不要标注「疑似刷量」，按正常项目评价即可。
7. 不要把「疑似刷量」作为降低评分的唯一理由；如果项目本身有明确价值，应正常推荐。
8. 末尾给出今日小结
{trend_requirement}{trend_section}

原始内容：
{items_text}"""

        return self._call_ai(prompt, ai_config, data)

    def _call_ai(self, prompt: str, ai_config: dict, data: list[dict]) -> str:
        content = call_chat_completion(prompt, ai_config, purpose="日报")
        sources = set(item["source"] for item in data if item.get("source"))
        source_str = "、".join(sources)
        return f"📡 数据来源: {source_str}\n\n{content}"
