"""配置校验测试——启动时的高风险路径."""

import unittest
from src.main import validate_config

VALID_AI = {"api_base": "http://test", "model": "gpt-4"}
VALID_EMAIL = {
    "smtp_server": "smtp.test.com",
    "smtp_port": 587,
    "username": "u",
    "password": "p",
    "recipient": "r@t.com",
}


def _cfg(**overrides):
    cfg = {
        "ai": dict(VALID_AI),
        "notifiers": {"email": dict(VALID_EMAIL)},
        "tasks": [
            {
                "name": "test",
                "schedule": "0 8 * * *",
                "collector": "github_trending",
                "processor": "summarizer",
                "notifier": "email",
            }
        ],
    }
    cfg.update(overrides)
    return cfg


class TestValidConfig(unittest.TestCase):
    def test_minimal_valid(self):
        validate_config(_cfg())

    def test_none_collector(self):
        t = {
            "name": "t",
            "schedule": "0 8 * * *",
            "collector": "none",
            "processor": "summarizer",
            "notifier": "email",
        }
        validate_config(_cfg(tasks=[t]))

    def test_weekly_with_task_name(self):
        t = {
            "name": "t",
            "schedule": "0 9 * * 0",
            "collector": "none",
            "processor": "weekly",
            "notifier": "email",
            "params": {"task_name": "daily"},
        }
        validate_config(_cfg(tasks=[t]))

    def test_save_trends_does_not_affect_validation(self):
        t = {
            "name": "t",
            "schedule": "0 8 * * *",
            "collector": "github_trending",
            "processor": "summarizer",
            "notifier": "email",
            "save_trends": False,
        }
        validate_config(_cfg(tasks=[t]))

    def test_telegram_valid(self):
        cfg = _cfg(
            notifiers={"telegram": {"bot_token": "x", "chat_id": "y"}},
            tasks=[{"name": "t", "schedule": "0 8 * * *", "collector": "none", "processor": "summarizer", "notifier": "telegram"}],
        )
        validate_config(cfg)

    def test_unused_notifier_env_placeholders_are_allowed(self):
        cfg = _cfg(
            notifiers={
                "email": dict(VALID_EMAIL),
                "telegram": {"bot_token": "${TELEGRAM_BOT_TOKEN}", "chat_id": "${TELEGRAM_CHAT_ID}"},
            }
        )
        validate_config(cfg)

    def test_multi_source_task_valid(self):
        task = {
            "name": "t",
            "schedule": "0 8 * * *",
            "sources": [
                {"collector": "github_trending", "params": {"max_articles": 3}},
                {"collector": "hacker_news", "params": {"query": "ai", "max_articles": 3}},
                {"collector": "arxiv", "params": {"query": "cat:cs.AI", "max_articles": 3}},
                {"collector": "hugging_face", "params": {"repo_type": "models", "max_articles": 3}},
                {"collector": "product_hunt", "params": {"max_articles": 3}},
                {"collector": "dev_to", "params": {"tag": "ai", "max_articles": 3}},
            ],
            "processor": "scored_summarizer",
            "notifier": "email",
        }
        validate_config(_cfg(tasks=[task]))


class TestMissingFields(unittest.TestCase):
    def test_missing_ai(self):
        with self.assertRaises(SystemExit):
            validate_config(_cfg(ai=None))

    def test_missing_ai_api_base(self):
        with self.assertRaises(SystemExit):
            validate_config(_cfg(ai={"model": "gpt-4"}))

    def test_missing_ai_model(self):
        with self.assertRaises(SystemExit):
            validate_config(_cfg(ai={"api_base": "http://t"}))


class TestEmailValidation(unittest.TestCase):
    def _task_cfg(self, **email_overrides):
        email = dict(VALID_EMAIL, **email_overrides)
        return _cfg(notifiers={"email": email})

    def test_missing_username(self):
        with self.assertRaises(SystemExit):
            validate_config(self._task_cfg(username=""))

    def test_missing_password(self):
        with self.assertRaises(SystemExit):
            validate_config(self._task_cfg(password=""))

    def test_missing_recipient(self):
        with self.assertRaises(SystemExit):
            validate_config(self._task_cfg(recipient=""))

    def test_missing_smtp_server(self):
        with self.assertRaises(SystemExit):
            validate_config(self._task_cfg(smtp_server=""))

    def test_invalid_smtp_port(self):
        with self.assertRaises(SystemExit):
            validate_config(self._task_cfg(smtp_port="abc"))

    def test_zero_smtp_port(self):
        with self.assertRaises(SystemExit):
            validate_config(self._task_cfg(smtp_port=0))


class TestTelegramValidation(unittest.TestCase):
    def _task_cfg(self, **tg_overrides):
        tg = {"bot_token": "x", "chat_id": "y"}
        tg.update(tg_overrides)
        return _cfg(
            notifiers={"telegram": tg},
            tasks=[{"name": "t", "schedule": "0 8 * * *", "collector": "none", "processor": "summarizer", "notifier": "telegram"}],
        )

    def test_missing_bot_token(self):
        with self.assertRaises(SystemExit):
            validate_config(self._task_cfg(bot_token=""))

    def test_missing_chat_id(self):
        with self.assertRaises(SystemExit):
            validate_config(self._task_cfg(chat_id=""))

    def test_used_notifier_env_placeholder_is_invalid(self):
        with self.assertRaises(SystemExit):
            validate_config(self._task_cfg(bot_token="${TELEGRAM_BOT_TOKEN}"))


class TestTaskValidation(unittest.TestCase):
    def test_weekly_missing_task_name(self):
        t = {
            "name": "t",
            "schedule": "0 9 * * 0",
            "collector": "none",
            "processor": "weekly",
            "notifier": "email",
            "params": {},
        }
        with self.assertRaises(SystemExit):
            validate_config(_cfg(tasks=[t]))

    def test_invalid_cron(self):
        t = {"name": "t", "schedule": "abc", "collector": "none", "processor": "summarizer", "notifier": "email"}
        with self.assertRaises(SystemExit):
            validate_config(_cfg(tasks=[t]))

    def test_empty_tasks(self):
        with self.assertRaises(SystemExit):
            validate_config(_cfg(tasks=[]))

    def test_unknown_collector(self):
        t = {"name": "t", "schedule": "0 8 * * *", "collector": "nope", "processor": "summarizer", "notifier": "email"}
        with self.assertRaises(SystemExit):
            validate_config(_cfg(tasks=[t]))

    def test_unknown_source_collector(self):
        t = {
            "name": "t",
            "schedule": "0 8 * * *",
            "sources": [{"collector": "nope"}],
            "processor": "summarizer",
            "notifier": "email",
        }
        with self.assertRaises(SystemExit):
            validate_config(_cfg(tasks=[t]))
