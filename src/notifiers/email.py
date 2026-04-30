import smtplib
from email.message import EmailMessage
from .base import Notifier
from ..logger import log


class EmailNotifier(Notifier):
    name = "email"

    def send(self, title: str, content: str, config: dict) -> bool:
        smtp_server = config.get("smtp_server", "smtp.gmail.com")
        smtp_port = config.get("smtp_port", 587)
        username = config.get("username")
        password = config.get("password")
        recipient = config.get("recipient")

        if not username or not password or not recipient:
            raise ValueError("邮件配置缺少 username、password 或 recipient")

        msg = EmailMessage()
        msg["From"] = username
        msg["To"] = recipient
        msg["Subject"] = title
        msg.set_content(content)

        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)
            log.info(f"邮件推送成功 -> {recipient}")
            return True
        except Exception as e:
            log.warning(f"邮件推送失败: {e}")
            return False
