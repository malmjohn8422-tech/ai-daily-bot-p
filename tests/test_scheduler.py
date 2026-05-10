"""调度器测试——报告归档、save_trends 开关、趋势历史日期窗口."""

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.reports import ReportArchive
from src.storage.sqlite import SQLiteStorage


# ── ReportArchive ─────────────────────────────────────────────────

class TestReportSlug:
    def test_basic_slug(self):
        assert ReportArchive._safe_slug("GitHub 开源早报") == "github-开源早报"

    def test_emoji_stripped(self):
        slug = ReportArchive._safe_slug("🐙 GitHub 开源早报")
        assert "github" in slug
        assert "🐙" not in slug

    def test_special_chars_replaced(self):
        slug = ReportArchive._safe_slug("a/b[c]d!e")
        assert slug == "a-b-c-d-e"

    def test_long_slug_truncated(self):
        long_name = "a-" * 30
        slug = ReportArchive._safe_slug(long_name)
        assert len(slug) <= 40


class TestReportArchive:
    def test_save_and_load(self, tmp_path):
        archive = ReportArchive(root=tmp_path)
        path = archive.save("test task", 1, "# hello", items=[{"title": "repo"}])
        assert archive.exists(path)
        assert archive.load(path) == "# hello"
        assert archive.load_items(path) == [{"title": "repo"}]

    def test_exists_none(self):
        assert not ReportArchive().exists(None)

    def test_exists_empty_string(self):
        assert not ReportArchive().exists("")

    def test_exists_missing_file(self):
        assert not ReportArchive().exists("reports/9999-99-99/nope.md")

    def test_load_items_missing_meta(self, tmp_path):
        archive = ReportArchive(root=tmp_path)
        md = tmp_path / "test.md"
        md.write_text("content", encoding="utf-8")
        # no .json sidecar
        assert archive.load_items(str(md)) == []

    def test_build_path_uses_record_id(self):
        archive = ReportArchive(root=Path("/tmp"))
        path = archive.build_path("test", 42)
        assert "000042" in str(path)

    def test_atomic_write_replaces_tmp(self, tmp_path):
        archive = ReportArchive(root=tmp_path)
        path = archive.save("t", 1, "content")
        assert not list(tmp_path.rglob("*.tmp"))  # no .tmp files left behind


# ── save_trends 开关 ──────────────────────────────────────────────

class TestSaveTrends:
    @patch("src.scheduler._prepare_report")
    @patch("src.scheduler.get_notifier")
    @patch("src.scheduler.storage")
    def test_save_trends_true_calls_storage(self, mock_storage, mock_notifier, mock_prepare):
        """save_trends 默认 True，通知成功后应调用 save_trend_items."""
        from src.scheduler import _execute_task

        mock_prepare.return_value = ("report", [{"title": "repo"}], "p")
        mock_notifier.return_value.send.return_value = True

        cfg = {"name": "t", "notifier": "email", "save_trends": True, "collector": "none"}
        _execute_task(cfg, {}, {"email": {}}, 1)
        mock_storage.save_trend_items.assert_called_once()

    @patch("src.scheduler._prepare_report")
    @patch("src.scheduler.get_notifier")
    @patch("src.scheduler.storage")
    def test_save_trends_false_skips_storage(self, mock_storage, mock_notifier, mock_prepare):
        """save_trends=False 时不应调用 save_trend_items."""
        from src.scheduler import _execute_task

        mock_prepare.return_value = ("report", [{"title": "repo"}], "p")
        mock_notifier.return_value.send.return_value = True

        cfg = {"name": "t", "notifier": "email", "save_trends": False, "collector": "none"}
        _execute_task(cfg, {}, {"email": {}}, 1)
        mock_storage.save_trend_items.assert_not_called()

    @patch("src.scheduler._prepare_report")
    @patch("src.scheduler.get_notifier")
    @patch("src.scheduler.storage")
    def test_save_trends_default_true(self, mock_storage, mock_notifier, mock_prepare):
        """未设置 save_trends 时默认 True."""
        from src.scheduler import _execute_task

        mock_prepare.return_value = ("report", [{"title": "repo"}], "p")
        mock_notifier.return_value.send.return_value = True

        cfg = {"name": "t", "notifier": "email", "collector": "none"}
        _execute_task(cfg, {}, {"email": {}}, 1)
        mock_storage.save_trend_items.assert_called_once()

    @patch("src.scheduler._prepare_report")
    @patch("src.scheduler.get_notifier")
    @patch("src.scheduler.storage")
    def test_empty_data_skips_storage(self, mock_storage, mock_notifier, mock_prepare):
        """data 为空列表时不应调用 save_trend_items."""
        from src.scheduler import _execute_task

        mock_prepare.return_value = ("report", [], "p")
        mock_notifier.return_value.send.return_value = True

        cfg = {"name": "t", "notifier": "email", "save_trends": True, "collector": "none"}
        _execute_task(cfg, {}, {"email": {}}, 1)
        mock_storage.save_trend_items.assert_not_called()


# ── 报告复用 ───────────────────────────────────────────────────────

class TestPrepareReportReuse:
    @patch("src.scheduler.report_archive")
    @patch("src.scheduler.storage")
    def test_reuses_existing_report(self, mock_storage, mock_archive):
        """当 report_path 存在时应复用而非重新生成."""
        from src.scheduler import _prepare_report

        mock_storage.get_report_path.return_value = "reports/existing.md"
        mock_archive.exists.return_value = True
        mock_archive.load.return_value = "cached content"
        mock_archive.load_items.return_value = [{"title": "cached"}]

        content, items, path = _prepare_report({"name": "t", "collector": "none"}, {}, 1)

        assert content == "cached content"
        assert items == [{"title": "cached"}]
        mock_archive.save.assert_not_called()


class TestMultiSourceFetch:
    @patch("src.scheduler.get_collector")
    def test_fetch_task_data_combines_sources(self, mock_get_collector):
        from src.scheduler import _fetch_task_data

        class GithubCollector:
            def fetch(self, params=None):
                return [{"title": "repo", "url": "u", "summary": "", "source": "GitHub", "extra": {}}]

        class HnCollector:
            def fetch(self, params=None):
                return [{"title": "story", "url": "u2", "summary": "", "source": "HN", "extra": {}}]

        mock_get_collector.side_effect = lambda name: {
            "github_trending": GithubCollector,
            "hacker_news": HnCollector,
        }[name]

        data = _fetch_task_data({
            "sources": [
                {"collector": "github_trending", "params": {"max_articles": 1}},
                {"collector": "hacker_news", "params": {"query": "ai"}},
            ]
        })

        assert [item["title"] for item in data] == ["repo", "story"]
        assert data[0]["extra"]["source_collector"] == "github_trending"
        assert data[1]["extra"]["source_collector"] == "hacker_news"

    @patch("src.scheduler.get_collector")
    def test_fetch_task_data_skips_optional_source_failures(self, mock_get_collector):
        from src.scheduler import _fetch_task_data

        class BrokenCollector:
            def fetch(self, params=None):
                raise RuntimeError("boom")

        class GoodCollector:
            def fetch(self, params=None):
                return [{"title": "ok", "url": "u", "summary": "", "source": "ok", "extra": {}}]

        mock_get_collector.side_effect = lambda name: {
            "broken": BrokenCollector,
            "good": GoodCollector,
        }[name]

        data = _fetch_task_data({
            "sources": [
                {"collector": "broken"},
                {"collector": "good"},
            ]
        })

        assert [item["title"] for item in data] == ["ok"]

    @patch("src.scheduler.get_collector")
    def test_fetch_task_data_raises_required_source_failures(self, mock_get_collector):
        from src.scheduler import _fetch_task_data

        class BrokenCollector:
            def fetch(self, params=None):
                raise RuntimeError("boom")

        mock_get_collector.return_value = BrokenCollector

        with pytest.raises(RuntimeError, match="boom"):
            _fetch_task_data({"sources": [{"collector": "broken", "required": True}]})


# ── 趋势历史日期窗口 ───────────────────────────────────────────────

class TestTrendHistoryDateWindow:
    """验证 get_trend_history 的日期范围逻辑：
    - end_date 是 exclusive（date < end）
    - 当 end_date = today + 1 时包含今天的数据
    """

    def test_end_date_is_exclusive(self, tmp_path):
        db = SQLiteStorage(str(tmp_path / "test.db"))

        item = {"title": "a/b", "url": "https://github.com/a/b", "summary": "", "source": "t", "extra": {"stars": 1}}
        db.save_trend_items("t", [item], run_date="2026-04-29")
        db.save_trend_items("t", [item], run_date="2026-04-30")

        # end=04-30 → date < 04-30 → 只包含 04-29
        r = db.get_trend_history("t", days=7, end_date=date(2026, 4, 30))
        assert "2026-04-29" in r
        assert "2026-04-30" not in r

    def test_daily_data_included_when_end_is_next_day(self, tmp_path):
        """模拟周报场景：周日运行，end_date = 周一，应包含周日数据"""
        db = SQLiteStorage(str(tmp_path / "test.db"))

        item = {"title": "a/b", "url": "https://github.com/a/b", "summary": "", "source": "t", "extra": {"stars": 1}}
        db.save_trend_items("t", [item], run_date="2026-04-26")  # 周日
        db.save_trend_items("t", [item], run_date="2026-04-27")  # 周一

        # end=04-27 → date < 04-27 → 包含 04-26（周日），不包含 04-27（周一）
        r = db.get_trend_history("t", days=7, end_date=date(2026, 4, 27))
        assert "2026-04-26" in r
        assert "2026-04-27" not in r

    def test_range_days_limits_results(self, tmp_path):
        db = SQLiteStorage(str(tmp_path / "test.db"))

        item = {"title": "a/b", "url": "https://github.com/a/b", "summary": "", "source": "t", "extra": {"stars": 1}}
        db.save_trend_items("t", [item], run_date="2026-04-01")
        db.save_trend_items("t", [item], run_date="2026-04-29")

        r = db.get_trend_history("t", days=3, end_date=date(2026, 5, 1))
        # 只取 04-28 ~ 04-30 的数据
        assert "2026-04-01" not in r
        assert "2026-04-29" in r

    def test_repo_detail_fields_are_preserved(self, tmp_path):
        db = SQLiteStorage(str(tmp_path / "test.db"))

        item = {
            "title": "a/b",
            "url": "https://github.com/a/b",
            "summary": "",
            "source": "t",
            "extra": {
                "stars": 100,
                "forks": 10,
                "language": "Python",
                "open_issues": 3,
                "watchers": 5,
                "repo_created_at": "2026-01-01T00:00:00Z",
                "repo_pushed_at": "2026-05-01T00:00:00Z",
                "license": "MIT",
                "topics": ["ai", "daily"],
                "archived": False,
            },
        }
        db.save_trend_items("t", [item], run_date="2026-04-29")

        r = db.get_trend_history("t", days=7, end_date=date(2026, 4, 30))
        saved = r["2026-04-29"][0]
        assert saved["open_issues"] == 3
        assert saved["watchers"] == 5
        assert saved["repo_pushed_at"] == "2026-05-01T00:00:00Z"
        assert saved["license"] == "MIT"
        assert saved["topics"] == '["ai", "daily"]'
