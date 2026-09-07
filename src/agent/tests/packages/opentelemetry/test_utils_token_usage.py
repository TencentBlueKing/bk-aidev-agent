# -*- coding: utf-8 -*-
"""``extract_token_usage`` 单元测试（多路径提取，等价 services/token_usage.py 逻辑）。"""

import pytest
from aidev_agent.packages.opentelemetry.utils import extract_token_usage
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult


class _DictLike:
    """实现 to_dict_recursive 归一化路径的自定义对象。"""

    def __init__(self, data: dict):
        self._data = data

    def to_dict_recursive(self) -> dict:
        return self._data


def test_extract_from_llm_output_token_usage():
    """Test 1: llm_output["token_usage"] 路径提取 input/output/total 三个 int。"""
    response = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
        llm_output={
            "model_name": "qwen3",
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
    )
    result = extract_token_usage(response)
    assert result == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}


def test_extract_from_llm_output_usage_key():
    """Test 2: llm_output["usage"] 备选 key 路径。"""
    response = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
        llm_output={"usage": {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7}},
    )
    result = extract_token_usage(response)
    assert result == {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7}


def test_extract_from_usage_metadata_path():
    """Test 3: generations[-1][-1].message.usage_metadata 路径（无 llm_output token_usage）。"""
    message = AIMessage(content="答案", usage_metadata={"input_tokens": 8, "output_tokens": 2, "total_tokens": 10})
    response = LLMResult(
        generations=[[ChatGeneration(message=message)]],
        llm_output={"model_name": "qwen3"},
    )
    result = extract_token_usage(response)
    assert result == {"input_tokens": 8, "output_tokens": 2, "total_tokens": 10}


def test_provider_key_aliases():
    """Test 4: provider key 别名 prompt_tokens / completion_tokens。"""
    response = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
        llm_output={"token_usage": {"prompt_tokens": 12, "completion_tokens": 6}},
    )
    result = extract_token_usage(response)
    assert result["input_tokens"] == 12
    assert result["output_tokens"] == 6


def test_total_tokens_derived():
    """Test 5: total_tokens 缺失时派生为 input+output。"""
    response = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
        llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}},
    )
    result = extract_token_usage(response)
    assert result["total_tokens"] == 15


def test_cache_read_to_cached_tokens():
    """Test 6: input_token_details["cache_read"] → cached_tokens。"""
    message = AIMessage(
        content="答案",
        usage_metadata={
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "input_token_details": {"cache_read": 7},
        },
    )
    response = LLMResult(
        generations=[[ChatGeneration(message=message)]],
        llm_output={"model_name": "qwen3"},
    )
    result = extract_token_usage(response)
    assert result["cached_tokens"] == 7
    assert "reasoning_tokens" not in result


def test_reasoning_to_reasoning_tokens():
    """Test 7: output_token_details["reasoning"] → reasoning_tokens。"""
    message = AIMessage(
        content="答案",
        usage_metadata={
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "output_token_details": {"reasoning": 3},
        },
    )
    response = LLMResult(
        generations=[[ChatGeneration(message=message)]],
        llm_output={"model_name": "qwen3"},
    )
    result = extract_token_usage(response)
    assert result["reasoning_tokens"] == 3
    assert "cached_tokens" not in result


@pytest.mark.parametrize(
    "details, expected_key, expected_value",
    [
        ({"prompt_tokens_details": {"cached_tokens": 9}}, "cached_tokens", 9),
        ({"completion_tokens_details": {"reasoning_tokens": 4}}, "reasoning_tokens", 4),
    ],
)
def test_provider_native_details_fallback(details, expected_key, expected_value):
    """Test 11: provider 原生 details 键（prompt_tokens_details / completion_tokens_details）回落提取。"""
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, **details}
    response = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
        llm_output={"token_usage": usage},
    )
    result = extract_token_usage(response)
    assert result[expected_key] == expected_value


@pytest.mark.parametrize(
    "details, expected",
    [
        (
            {"input_token_details": {"cache_read": 3}, "prompt_tokens_details": {"cached_tokens": 9}},
            {"cached_tokens": 3},
        ),
        (
            {"output_token_details": {"reasoning": 1}, "completion_tokens_details": {"reasoning_tokens": 7}},
            {"reasoning_tokens": 1},
        ),
    ],
)
def test_normalized_details_take_precedence_over_provider_keys(details, expected):
    """Test 12: 归一化 key 与 provider 原生 key 同时存在时归一化优先（or 短路语义）。"""
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, **details}
    response = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
        llm_output={"token_usage": usage},
    )
    result = extract_token_usage(response)
    for key, value in expected.items():
        assert result[key] == value


def test_coerce_usage_dict_paths():
    """Test 8: to_dict_recursive / model_dump / dict 归一化（对象 → dict）。"""
    response = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
        llm_output={"token_usage": _DictLike({"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5})},
    )
    result = extract_token_usage(response)
    assert result == {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5}


def test_no_usage_returns_none():
    """Test 9: 无 usage 时返回 None。"""
    response = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
        llm_output={"model_name": "qwen3"},
    )
    assert extract_token_usage(response) is None


def test_int_normalization_safe_fallback():
    """Test 10: int() 归一化字符串/浮点，非数字安全回落 0。"""
    response = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
        llm_output={"token_usage": {"prompt_tokens": "10", "completion_tokens": 5.5}},
    )
    result = extract_token_usage(response)
    assert result["input_tokens"] == 10
    assert result["output_tokens"] == 5
