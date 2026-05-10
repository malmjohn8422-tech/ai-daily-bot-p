import time

import httpx

from .logger import log


RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class AIClientError(RuntimeError):
    """Raised when the configured chat completion endpoint cannot return text."""


def _should_retry(exc: Exception) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRY_STATUS_CODES
    return False


def call_chat_completion(
    prompt: str,
    ai_config: dict,
    *,
    purpose: str = "AI",
    max_attempts: int = 3,
    timeout: float = 120,
) -> str:
    """Call an OpenAI-compatible chat completions endpoint and return message text."""
    payload = {
        "model": ai_config.get("model", "gpt-4o"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": ai_config.get("temperature", 0.7),
    }

    headers = {"Content-Type": "application/json"}
    if ai_config.get("api_key"):
        headers["Authorization"] = f"Bearer {ai_config['api_key']}"

    api_base = ai_config.get("api_base")
    if not api_base:
        raise AIClientError("AI 配置缺少 api_base")

    log.info(f"调用AI模型 ({purpose}): {payload['model']}")
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = httpx.post(api_base, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise AIClientError("AI 响应内容为空")
            return content
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            last_exc = e
            if attempt < max_attempts and _should_retry(e):
                wait = 2 * (2 ** (attempt - 1))
                log.warning(f"{purpose} 第{attempt}次调用失败: {e}, {wait}s后重试")
                time.sleep(wait)
                continue
            break
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise AIClientError(f"AI 响应格式异常: {e}") from e

    raise AIClientError(f"{purpose} 调用失败: {last_exc}") from last_exc
