from unittest.mock import patch

import httpx
import pytest

from src.ai_client import AIClientError, call_chat_completion


def _response(status_code: int, payload: dict | None = None) -> httpx.Response:
    request = httpx.Request("POST", "https://ai.example/v1/chat/completions")
    return httpx.Response(status_code, json=payload or {}, request=request)


def test_call_chat_completion_returns_content():
    with patch("src.ai_client.httpx.post") as post:
        post.return_value = _response(
            200,
            {"choices": [{"message": {"content": "ok"}}]},
        )

        result = call_chat_completion(
            "prompt",
            {"api_base": "https://ai.example/v1/chat/completions", "model": "gpt"},
        )

    assert result == "ok"
    assert post.call_args.kwargs["json"]["model"] == "gpt"


def test_call_chat_completion_retries_retryable_status():
    with patch("src.ai_client.time.sleep") as sleep, patch("src.ai_client.httpx.post") as post:
        post.side_effect = [
            _response(429, {"error": "rate limited"}),
            _response(200, {"choices": [{"message": {"content": "ok"}}]}),
        ]

        result = call_chat_completion(
            "prompt",
            {"api_base": "https://ai.example/v1/chat/completions", "model": "gpt"},
        )

    assert result == "ok"
    sleep.assert_called_once_with(2)


def test_call_chat_completion_rejects_bad_response_shape():
    with patch("src.ai_client.httpx.post") as post:
        post.return_value = _response(200, {"unexpected": []})

        with pytest.raises(AIClientError, match="响应格式异常"):
            call_chat_completion(
                "prompt",
                {"api_base": "https://ai.example/v1/chat/completions", "model": "gpt"},
            )

