import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from aidev_agent.exceptions import (
    AgentException,
    extract_error_message,
    extract_exception_status_fields,
    extract_model_error_message,
)
from openai import RateLimitError

NESTED_MULTIMODAL = (
    "Error code: 400 - {'error': {'message': \"Error code: 400 - {'error': "
    "{'message': 'DeepSeek-V4-Flash is not a multimodal model', "
    "'type': 'BadRequestError', 'param': None, 'code': 400}}\", "
    "'code': 400, 'type': 'BadRequestError'}, "
    "'trace_id': '759ed94f628bcc1ba1ec7c3ad9e98e6e'}"
)
FRIENDLY_MULTIMODAL = "当前模型 DeepSeek-V4-Flash 不支持图片或文档输入。请更换支持多模态的模型，或移除附件后再试。"
RATE_LIMIT_BODY = {"code": 1642903, "code_name": "RATE_LIMIT_RESTRICTION", "message": "limited"}


def _rate_limit_error(body=RATE_LIMIT_BODY) -> RateLimitError:
    request = httpx.Request("POST", "https://example.com/v1/chat/completions")
    response = httpx.Response(429, request=request, json=body)
    return RateLimitError("Error responded by Backend api", response=response, body=body)


class TestExtractModelErrorMessage:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (NESTED_MULTIMODAL, FRIENDLY_MULTIMODAL),
            (
                "Authentication failed for model gptoss-999b",
                "模型调用异常: Authentication failed for model gptoss-999b",
            ),
            ("Error code: 400 - {'error': {'code': 400, 'type': 'BadRequestError'}}", "模型调用失败"),
        ],
    )
    def test_extract_model_error_message(self, raw, expected):
        message = extract_model_error_message(SimpleNamespace(message=raw))
        assert message == expected
        assert "Error code:" not in message
        assert "trace_id" not in message

    def test_extract_error_message_unwraps_nested_dict(self):
        assert extract_error_message(NESTED_MULTIMODAL) == "DeepSeek-V4-Flash is not a multimodal model"

    def test_streaming_json_uses_friendly_message(self):
        from aidev_agent.exceptions import streaming_chunk_exception_handling

        payload = json.loads(streaming_chunk_exception_handling(SimpleNamespace(message=NESTED_MULTIMODAL))[6:])
        assert payload["message"] == FRIENDLY_MULTIMODAL


class TestExtractExceptionStatusFields:
    @pytest.mark.parametrize(
        ("factory", "expected"),
        [
            (lambda: _rate_limit_error(), (429, 1642903, "RATE_LIMIT_RESTRICTION")),
            (lambda: RuntimeError("plain"), (None, None, None)),
        ],
    )
    def test_extract_exception_status_fields(self, factory, expected):
        assert extract_exception_status_fields(factory()) == expected

    def test_extract_follows_cause_chain(self):
        try:
            raise RuntimeError("wrap") from _rate_limit_error()
        except RuntimeError as wrapped:
            assert extract_exception_status_fields(wrapped) == (429, 1642903, "RATE_LIMIT_RESTRICTION")

    def test_extract_http_error_response_json(self):
        response = MagicMock()
        response.status_code = 429
        response.json.return_value = RATE_LIMIT_BODY
        error = Exception("http")
        error.response = response
        assert extract_exception_status_fields(error) == (429, 1642903, "RATE_LIMIT_RESTRICTION")

    def test_agent_exception_from_exception_keeps_fields(self):
        source = _rate_limit_error()
        wrapped = AgentException.from_exception(source, message=f"Error executing agent: {source}")
        assert (wrapped.status_code, wrapped.code, wrapped.code_name) == (429, 1642903, "RATE_LIMIT_RESTRICTION")
        assert "Error executing agent:" in wrapped.message
