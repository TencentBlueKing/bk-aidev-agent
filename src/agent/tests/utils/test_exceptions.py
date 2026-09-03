import json
from types import SimpleNamespace

import pytest
from aidev_agent.exceptions import extract_error_message, extract_model_error_message

NESTED_MULTIMODAL = (
    "Error code: 400 - {'error': {'message': \"Error code: 400 - {'error': "
    "{'message': 'DeepSeek-V4-Flash is not a multimodal model', "
    "'type': 'BadRequestError', 'param': None, 'code': 400}}\", "
    "'code': 400, 'type': 'BadRequestError'}, "
    "'trace_id': '759ed94f628bcc1ba1ec7c3ad9e98e6e'}"
)
FRIENDLY_MULTIMODAL = "当前模型 DeepSeek-V4-Flash 不支持图片或文档输入。请更换支持多模态的模型，或移除附件后再试。"


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
