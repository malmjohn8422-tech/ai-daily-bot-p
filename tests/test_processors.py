from unittest.mock import patch

from src.processors.summarizer import SummarizerProcessor
from src.processors.scored_summarizer import ScoredSummarizerProcessor
from src.processors.weekly import WeeklySummarizerProcessor


def test_summarizer_prompt_includes_repo_signals_for_conservative_judgement():
    data = [
        {
            "title": "owner/repo",
            "url": "https://github.com/owner/repo",
            "summary": "",
            "source": "GitHub Trending",
            "extra": {
                "stars": 1000,
                "forks": 125,
                "language": "Python",
                "watchers": 50,
                "open_issues": 10,
                "repo_pushed_at": "2026-05-01T00:00:00Z",
                "license": "MIT",
                "topics": ["ai", "tools"],
            },
        }
    ]

    with patch("src.processors.summarizer.call_chat_completion") as call_ai:
        call_ai.return_value = "report"
        SummarizerProcessor().process(data, {"api_base": "https://ai.example", "model": "gpt"})

    prompt = call_ai.call_args.args[0]
    assert "Stars: 1000" in prompt
    assert "Forks: 125" in prompt
    assert "Fork/Star 比例: 0.125" in prompt
    assert "Watchers: 50" in prompt
    assert "最近提交: 2026-05-01T00:00:00Z" in prompt
    assert "Topics: ai, tools" in prompt
    assert "证据不足时不要标注「疑似刷量」" in prompt


def test_scored_summarizer_prompt_includes_preferences_and_filtering_rules():
    data = [
        {
            "title": "AI tool",
            "url": "https://example.com",
            "summary": "useful",
            "source": "Hacker News",
            "extra": {"score": 10, "comments": 2},
        }
    ]
    params = {
        "preferences": {
            "min_score": 8,
            "interests": ["AI and LLM applications", "developer tools"],
            "exclude": ["NFT", "pure marketing"],
        }
    }

    with patch("src.processors.scored_summarizer.call_chat_completion") as call_ai:
        call_ai.return_value = "report"
        ScoredSummarizerProcessor().process(data, {"api_base": "https://ai.example", "model": "gpt"}, params)

    prompt = call_ai.call_args.args[0]
    assert "最低推荐分: 8/10" in prompt
    assert "AI and LLM applications, developer tools" in prompt
    assert "尽量过滤: NFT, pure marketing" in prompt
    assert "题材不限" in prompt
    assert "不是 AI、LLM 或开发工具就天然降分" in prompt
    assert "AI/LLM 应用、开发者工具、自动化、agents" in prompt
    assert "NFT 相关内容默认过滤" in prompt
    assert "已过滤" in prompt


def test_scored_summarizer_limits_items_and_trims_long_summaries():
    data = [
        {
            "title": f"item-{i}",
            "url": "https://example.com",
            "summary": "x" * 1000,
            "source": "Dev.to",
            "extra": {},
        }
        for i in range(3)
    ]

    with patch("src.processors.scored_summarizer.call_chat_completion") as call_ai:
        call_ai.return_value = "report"
        ScoredSummarizerProcessor().process(
            data,
            {"api_base": "https://ai.example", "model": "gpt"},
            {"max_items": 2},
        )

    prompt = call_ai.call_args.args[0]
    assert "item-0" in prompt
    assert "item-1" in prompt
    assert "item-2" not in prompt
    assert "x" * 800 not in prompt


def test_weekly_history_aliases_are_merged(monkeypatch):
    calls = []

    def fake_history(task_name, days=7, end_date=None):
        calls.append(task_name)
        if task_name == "new":
            return {"2026-05-01": [{"title": "repo", "url": "u"}]}
        if task_name == "old":
            return {
                "2026-05-01": [{"title": "repo", "url": "u"}],
                "2026-05-02": [{"title": "old-only", "url": "u2"}],
            }
        return {}

    import src.processors.weekly as weekly_module

    monkeypatch.setattr(weekly_module.storage, "get_trend_history", fake_history)

    result = WeeklySummarizerProcessor()._load_history(
        {"task_name": "new", "history_aliases": ["old"]},
        report_end="2026-05-03",
    )

    assert calls == ["new", "old"]
    assert len(result["2026-05-01"]) == 1
    assert result["2026-05-02"][0]["title"] == "old-only"
