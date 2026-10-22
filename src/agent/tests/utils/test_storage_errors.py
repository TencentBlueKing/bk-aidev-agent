import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aidev_agent.exceptions import (
    AgentException,
    KnowledgeStorageReadError,
    extract_model_error_message,
    extract_storage_read_error,
    streaming_chunk_exception_handling,
)
from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.pydantic_models import KnowledgeSettings
from requests import Response
from requests.exceptions import HTTPError

TRACE_ID = "a" * 32


@pytest.fixture
def storage_failure():
    def build(status=429):
        response = Response()
        response.status_code = 503
        response._content = json.dumps(
            {
                "error": {
                    "code": "STORAGE_READ_ERROR",
                    "message": "private/path?token=secret",
                    "data": {"upstream_status_code": status},
                    "trace_id": TRACE_ID,
                }
            }
        ).encode()
        return HTTPError("private/path?token=secret", response=response)

    return build


@pytest.mark.parametrize("status", [403, 429, 503, None])
def test_storage_error_survives_agent_and_stream_wrapping(storage_failure, status):
    original = storage_failure(status)
    wrapped = AgentException.from_exception(original)
    payload = json.loads(streaming_chunk_exception_handling(wrapped)[6:])

    assert payload["code"] == "STORAGE_READ_ERROR"
    assert payload["status_code"] == 503
    assert payload["upstream_status_code"] == status
    assert payload["trace_id"] == TRACE_ID
    assert "知识库文档读取失败" in payload["message"]
    assert "模型调用" not in payload["message"]
    assert "secret" not in payload["message"]
    assert TRACE_ID in payload["message"]


def test_retriever_raises_safe_tool_error(storage_failure):
    failure = storage_failure()
    manager = Mock()
    manager.knowledge_query.side_effect = failure

    with pytest.raises(KnowledgeStorageReadError) as raised:
        BkRetriever(manager).query_knowledge("query", KnowledgeSettings())

    assert raised.value.__cause__ is failure
    assert "存储服务限流" in str(raised.value)
    assert "429" in str(raised.value)
    assert TRACE_ID in str(raised.value)
    assert "secret" not in str(raised.value)
    manager.knowledge_query.assert_called_once()


def test_direct_platform_exception_and_nested_cause_are_recognized():
    original = Exception("private/path")
    original.code = "STORAGE_READ_ERROR"
    original.data = {"upstream_status_code": 429, "trace_id": TRACE_ID}
    wrapped = RuntimeError("tool failed")
    wrapped.__cause__ = original

    error = extract_storage_read_error(wrapped)

    assert error.upstream_status_code == 429
    assert error.trace_id == TRACE_ID
    assert "模型调用" not in extract_model_error_message(wrapped)


def test_other_errors_are_not_classified_by_message_keywords():
    error = SimpleNamespace(message="STORAGE_READ_ERROR 429")
    assert extract_storage_read_error(error) is None
    assert extract_model_error_message(error) == "模型调用异常: STORAGE_READ_ERROR 429"


def test_in_process_platform_storage_exception_keeps_its_type():
    original = Exception("知识库文档读取失败")
    original.code = "STORAGE_READ_ERROR"
    original.data = {"upstream_status_code": 429, "trace_id": TRACE_ID}
    manager = Mock()
    manager.knowledge_query.side_effect = original

    with pytest.raises(Exception) as raised:
        BkRetriever(manager).query_knowledge("query", KnowledgeSettings())

    assert raised.value is original


@pytest.mark.parametrize("trace_id", [None, "not-a-trace", 123])
def test_typed_storage_error_discards_invalid_trace(trace_id):
    error = KnowledgeStorageReadError(status_code=503, upstream_status_code=429, trace_id=trace_id)
    assert extract_storage_read_error(error) is error
    assert error.trace_id is None
    assert "not-a-trace" not in str(error)


def test_exception_group_keeps_storage_error_details(storage_failure):
    error = ExceptionGroup("parallel requests", [ValueError("other"), storage_failure()])
    payload = json.loads(streaming_chunk_exception_handling(error)[6:])
    assert payload["upstream_status_code"] == 429
    assert payload["trace_id"] == TRACE_ID
    assert "secret" not in payload["message"]


def test_malformed_details_are_not_rendered_or_mistaken_for_metadata():
    error = Exception("private/path")
    error.body = {"error": {"code": "STORAGE_READ_ERROR", "data": ["secret"], "trace_id": "invalid"}}
    extracted = extract_storage_read_error(error)
    assert extracted.upstream_status_code is None
    assert extracted.trace_id is None
    assert "private/path" not in str(extracted)
    assert "secret" not in str(extracted)


def test_direct_platform_exception_preserves_http_status_in_stream():
    error = Exception("知识库文档读取失败")
    error.code = "STORAGE_READ_ERROR"
    error.STATUS_CODE = 503
    error.data = {"upstream_status_code": 429, "trace_id": TRACE_ID}
    payload = json.loads(streaming_chunk_exception_handling(AgentException.from_exception(error))[6:])
    assert payload["status_code"] == 503
    assert payload["upstream_status_code"] == 429
    assert payload["trace_id"] == TRACE_ID
