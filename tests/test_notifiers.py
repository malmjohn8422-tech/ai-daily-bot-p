"""通知器测试——Email HTML 转义、Telegram 分段."""

import unittest
from src.notifiers.email import _to_html
from src.notifiers.telegram import TelegramNotifier


# ── Email HTML 转义 ──────────────────────────────────────────────

class TestEmailHtmlEscape(unittest.TestCase):
    def test_plain_text_preserved(self):
        html = _to_html("标题", "hello world")
        assert "hello world" in html

    def test_special_chars_escaped(self):
        html = _to_html("标题", "a < b & c > d")
        assert "&lt;" in html
        assert "&amp;" in html
        assert "&gt;" in html
        assert "< b" not in html

    def test_title_escaped(self):
        html = _to_html("标题 <script>", "内容")
        assert "&lt;script&gt;" in html
        assert "<script>" not in html

    def test_url_converted_to_link(self):
        html = _to_html("标题", "check https://github.com/a/b")
        assert 'href="https://github.com/a/b"' in html
        assert "<a " in html

    def test_url_with_query_params(self):
        html = _to_html("标题", "https://example.com?a=1&b=2")
        # & in URL should be escaped in href attribute
        assert "&amp;b=2" in html

    def test_multiline_content(self):
        content = "【1】repo\n简介\n推荐：★★★★★\n## 趋势"
        html = _to_html("标题", content)
        assert "【1】repo" in html
        assert "简介" in html
        assert "★★★★★" in html

    def test_empty_content_returns_valid_html(self):
        html = _to_html("标题", "")
        assert html.startswith("<!DOCTYPE html>")


# ── Telegram 消息分段 ────────────────────────────────────────────

class TestTelegramSplit(unittest.TestCase):
    MAX_LEN = 3900

    def make_notifier(self):
        n = TelegramNotifier()
        return n

    def test_under_limit_single_chunk(self):
        n = self.make_notifier()
        text = "x" * (self.MAX_LEN - 100)
        chunks = n._split_text(text)
        assert len(chunks) == 1

    def test_at_limit_single_chunk(self):
        n = self.make_notifier()
        text = "x" * self.MAX_LEN
        chunks = n._split_text(text)
        assert len(chunks) == 1

    def test_over_limit_split(self):
        n = self.make_notifier()
        text = "x" * (self.MAX_LEN + 100)
        chunks = n._split_text(text)
        assert len(chunks) == 2
        assert len(chunks[0]) <= self.MAX_LEN
        assert len(chunks[1]) <= self.MAX_LEN

    def test_no_data_loss(self):
        n = self.make_notifier()
        text = "hello\n" * 1000
        joined = "".join(n._split_text(text))
        # The original trailing newline may be split — compare stripped
        assert joined.rstrip("\n") == text.rstrip("\n")
        assert len(joined) >= len(text) - self.MAX_LEN  # at most one chunk's worth of overlap

    def test_single_line_longer_than_max(self):
        n = self.make_notifier()
        text = "x" * (self.MAX_LEN + 500)
        chunks = n._split_text(text)
        assert len(chunks) == 2
        assert all(len(c) <= self.MAX_LEN for c in chunks)

    def test_line_breaks_preserved(self):
        n = self.make_notifier()
        text = "line1\n\nline3\nline4"
        chunks = n._split_text(text)
        restored = "".join(chunks)
        assert "line1" in restored
        assert "line3" in restored
        assert "line4" in restored
