import smtplib
import re
import html
from email.message import EmailMessage
from .base import Notifier
from ..logger import log


URL_RE = re.compile(r"https?://[^\s<>'\"）)》】,，]+")


def _url_to_link(text: str) -> str:
    """将纯文本 URL 转为可点击的 HTML 链接"""
    parts = []
    pos = 0
    for match in URL_RE.finditer(text):
        url = match.group(0)
        parts.append(html.escape(text[pos:match.start()]))
        safe_url = html.escape(url, quote=True)
        parts.append(
            f'<a href="{safe_url}" style="color:#2563eb;word-break:break-all">{safe_url}</a>'
        )
        pos = match.end()
    parts.append(html.escape(text[pos:]))
    return "".join(parts)


def _to_html(title: str, content: str) -> str:
    lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            lines.append("<p style='margin:4px 0'>&nbsp;</p>")
        elif stripped.startswith("【") and "】" in stripped:
            # 项目标题行
            lines.append(
                f'<p style="margin:10px 0 2px;font-size:15px;font-weight:bold;color:#111">'
                f'{_url_to_link(stripped)}</p>'
            )
        elif stripped == "---":
            lines.append(
                f'<hr style="border:none;border-top:1px solid #e5e7eb;margin:12px 0">'
            )
        elif stripped.startswith("📡"):
            lines.append(
                f'<p style="margin:2px 0 10px;font-size:12px;color:#777">{_url_to_link(stripped)}</p>'
            )
        elif stripped.startswith("##"):
            # 小标题
            lines.append(
                f'<p style="margin:12px 0 4px;font-size:14px;font-weight:bold;color:#333">'
                f'{_url_to_link(stripped)}</p>'
            )
        elif stripped.startswith("推荐") or "推荐：" in stripped:
            lines.append(
                f'<p style="margin:2px 0;font-size:14px;color:#d97706">{_url_to_link(stripped)}</p>'
            )
        else:
            text = _url_to_link(stripped)
            lines.append(f'<p style="margin:2px 0;font-size:14px;color:#444">{text}</p>')

    body = "".join(lines)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f9fafb">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
<div style="border-bottom:2px solid #2563eb;padding-bottom:8px;margin-bottom:12px">
<p style="margin:0;font-size:18px;font-weight:bold;color:#2563eb">{html.escape(title)}</p>
</div>
{body}
<div style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:8px">
<p style="margin:0;font-size:12px;color:#999">AI Daily Bot · 自动生成，仅供参考</p>
</div>
</div>
</body>
</html>"""


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
        msg.add_alternative(_to_html(title, content), subtype="html")

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
