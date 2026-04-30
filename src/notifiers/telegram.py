import httpx
from .base import NotificationPartialFailure, Notifier
from ..logger import log


class TelegramNotifier(Notifier):
    name = "telegram"
    # Telegram sendMessage limit is 4096 chars. Keep headroom for Unicode/counting differences.
    MAX_LEN = 3900

    def _split_text(self, text: str) -> list[str]:
        """Split long Telegram messages by line, with hard cuts for oversized lines."""
        if len(text) <= self.MAX_LEN:
            return [text]

        chunks = []
        chunk = ""

        for line in text.splitlines(keepends=True):
            while len(line) > self.MAX_LEN:
                if chunk:
                    chunks.append(chunk)
                    chunk = ""
                chunks.append(line[:self.MAX_LEN])
                line = line[self.MAX_LEN:]

            if len(chunk) + len(line) > self.MAX_LEN:
                if chunk:
                    chunks.append(chunk)
                chunk = line
            else:
                chunk += line

        if chunk:
            chunks.append(chunk)

        return chunks

    def _split_and_send(self, bot_token: str, chat_id: str, text: str):
        """分段发送长消息；已部分发送后失败则交给调度器记录失败，避免整单重试重复推送。"""
        chunks = self._split_text(text)
        sent = 0

        for chunk in chunks:
            try:
                self._send_chunk(bot_token, chat_id, chunk)
                sent += 1
            except Exception as e:
                if sent:
                    raise NotificationPartialFailure(
                        f"Telegram 推送已发送 {sent}/{len(chunks)} 段后失败: {e}"
                    ) from e
                raise

    def _send_chunk(self, bot_token: str, chat_id: str, text: str):
        resp = httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        resp.raise_for_status()

    def send(self, title: str, content: str, config: dict) -> bool:
        bot_token = config.get("bot_token")
        chat_id = config.get("chat_id")
        if not bot_token or not chat_id:
            raise ValueError("Telegram 推送缺少 bot_token 或 chat_id")

        text = f"{title}\n\n{content}"

        try:
            self._split_and_send(bot_token, chat_id, text)
            return True
        except NotificationPartialFailure:
            raise
        except Exception as e:
            log.warning(f"Telegram 推送失败: {e}")
            return False
