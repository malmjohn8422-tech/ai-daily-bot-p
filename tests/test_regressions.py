import gc
import tempfile
import time
import unittest
from pathlib import Path

from src import scheduler
from src.main import validate_config
from src.notifiers.email import _to_html
from src.notifiers.telegram import TelegramNotifier
from src.reports import ReportArchive
from src.storage.sqlite import SQLiteStorage


class EmailRenderingTests(unittest.TestCase):
    def test_email_html_escapes_content_and_links_urls(self):
        html = _to_html("T<bad>", "hello <b>raw</b> & https://example.com/?q=x&n=1")

        self.assertNotIn("T<bad>", html)
        self.assertNotIn("<b>raw</b>", html)
        self.assertIn("T&lt;bad&gt;", html)
        self.assertIn("&lt;b&gt;raw&lt;/b&gt;", html)
        self.assertIn("https://example.com/?q=x&amp;n=1", html)


class TelegramTests(unittest.TestCase):
    def test_long_single_line_is_split(self):
        notifier = TelegramNotifier()
        chunks = notifier._split_text("x" * 5001)

        self.assertEqual([3900, 1101], [len(chunk) for chunk in chunks])
        self.assertTrue(all(len(chunk) <= notifier.MAX_LEN for chunk in chunks))


class StorageTests(unittest.TestCase):
    def test_trend_history_excludes_end_date_and_preserves_metric(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "history.db"
            storage = SQLiteStorage(str(db_path))
            storage.save_trend_items(
                "daily",
                [{"title": "today", "url": "u", "extra": {"stars": 1}}],
                run_date="2026-04-30",
            )
            storage.save_trend_items(
                "daily",
                [{"title": "old", "url": "u", "extra": {"stars": 2}}],
                run_date="2026-04-29",
            )
            storage.save_trend_items(
                "hn",
                [{"title": "hn", "url": "u", "extra": {"score": 99}}],
                run_date="2026-04-29",
            )

            history = storage.get_trend_history("daily", days=7, end_date="2026-04-30")
            hn_history = storage.get_trend_history("hn", days=7, end_date="2026-04-30")

            self.assertNotIn("2026-04-30", history)
            self.assertEqual("old", history["2026-04-29"][0]["title"])
            self.assertEqual("score", hn_history["2026-04-29"][0]["metric_name"])
            self.assertEqual(99, hn_history["2026-04-29"][0]["metric_value"])

            del storage
            gc.collect()
            time.sleep(0.1)


class ConfigValidationTests(unittest.TestCase):
    def test_email_required_fields_are_validated(self):
        cfg = {
            "ai": {"api_base": "http://example/v1/chat/completions", "api_key": "", "model": "gpt"},
            "notifiers": {
                "email": {
                    "smtp_server": "smtp.example.com",
                    "smtp_port": 587,
                    "username": "",
                    "password": "",
                    "recipient": "",
                }
            },
            "tasks": [
                {
                    "name": "daily",
                    "schedule": "0 8 * * *",
                    "collector": "github_trending",
                    "processor": "summarizer",
                    "notifier": "email",
                }
            ],
        }

        with self.assertRaises(SystemExit):
            validate_config(cfg)


class ReportArchiveTests(unittest.TestCase):
    def test_archive_saves_markdown_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = ReportArchive(tmp)
            path = archive.save(
                "Daily GitHub",
                12,
                "report body",
                [{"title": "repo", "url": "https://example.com"}],
            )

            self.assertEqual("report body", archive.load(path))
            self.assertEqual("repo", archive.load_items(path)[0]["title"])
            self.assertTrue(Path(path).is_file())


class SchedulerReportReuseTests(unittest.TestCase):
    def test_retry_reuses_archived_report_instead_of_calling_ai_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = ReportArchive(tmp)

            class FakeStorage:
                def __init__(self):
                    self.report_path = None
                    self.successes = 0
                    self.failures = 0
                    self.saved_trends = 0

                def record_start(self, task_name):
                    return 42

                def get_report_path(self, record_id):
                    return self.report_path

                def record_report(self, record_id, report_path):
                    self.report_path = report_path

                def get_trend_history(self, task_name, days=7):
                    return {}

                def save_trend_items(self, task_name, items):
                    self.saved_trends += 1

                def record_success(self, record_id, summary):
                    self.successes += 1

                def record_failure(self, record_id, error):
                    self.failures += 1

            class FakeCollector:
                calls = 0

                def fetch(self, params=None):
                    FakeCollector.calls += 1
                    return [{"title": "repo", "url": "u", "summary": "", "source": "x", "extra": {"stars": 1}}]

            class FakeProcessor:
                calls = 0

                def process(self, data, ai_config, params=None):
                    FakeProcessor.calls += 1
                    return "report body"

            class FakeNotifier:
                calls = 0

                def send(self, title, content, config):
                    FakeNotifier.calls += 1
                    return FakeNotifier.calls > 1

            fake_storage = FakeStorage()
            originals = {
                "storage": scheduler.storage,
                "report_archive": scheduler.report_archive,
                "get_collector": scheduler.get_collector,
                "get_processor": scheduler.get_processor,
                "get_notifier": scheduler.get_notifier,
                "sleep": scheduler.sleep,
            }
            try:
                scheduler.storage = fake_storage
                scheduler.report_archive = archive
                scheduler.get_collector = lambda name: FakeCollector
                scheduler.get_processor = lambda name: FakeProcessor
                scheduler.get_notifier = lambda name: FakeNotifier
                scheduler.sleep = lambda seconds: None

                scheduler.run_task(
                    {
                        "name": "daily",
                        "collector": "github_trending",
                        "processor": "summarizer",
                        "notifier": "email",
                    },
                    {},
                    {"email": {}},
                )
            finally:
                scheduler.storage = originals["storage"]
                scheduler.report_archive = originals["report_archive"]
                scheduler.get_collector = originals["get_collector"]
                scheduler.get_processor = originals["get_processor"]
                scheduler.get_notifier = originals["get_notifier"]
                scheduler.sleep = originals["sleep"]

            self.assertEqual(1, FakeCollector.calls)
            self.assertEqual(1, FakeProcessor.calls)
            self.assertEqual(2, FakeNotifier.calls)
            self.assertEqual(1, fake_storage.successes)
            self.assertEqual(0, fake_storage.failures)
            self.assertEqual(1, fake_storage.saved_trends)


if __name__ == "__main__":
    unittest.main()
