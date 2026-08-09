# -*- coding: utf-8 -*-
"""``get_otel_endpoint_by_agent_info`` / ``get_otel_endpoint_by_json_str`` / ``get_otel_endpoint_by_env`` 单元测试。"""

import pytest
from aidev_agent.packages.opentelemetry.utils import (
    get_otel_endpoint_by_agent_info,
    get_otel_endpoint_by_env,
    get_otel_endpoint_by_json_str,
    get_otel_endpoints_base_config,
)

# ── get_otel_endpoints_base_config ───────────────────────────────────


def test_get_otel_endpoints_base_config_defaults(monkeypatch):
    for key in (
        "BKAI_AGENT_BATCH_MAX_QUEUE_SIZE",
        "BKAI_AGENT_BATCH_SCHEDULE_DELAY_MILLIS",
        "BKAI_AGENT_BATCH_EXPORT_TIMEOUT_MILLIS",
        "BKAI_AGENT_BATCH_MAX_EXPORT_BATCH_SIZE",
    ):
        monkeypatch.delenv(key, raising=False)
    config = get_otel_endpoints_base_config()
    assert config == {
        "batch_max_queue_size": 2048,
        "batch_schedule_delay_millis": 5000,
        "batch_export_timeout_millis": 30000,
        "batch_max_export_batch_size": 512,
    }


def test_get_otel_endpoints_base_config_custom(monkeypatch):
    monkeypatch.setenv("BKAI_AGENT_BATCH_MAX_QUEUE_SIZE", "1024")
    monkeypatch.setenv("BKAI_AGENT_BATCH_MAX_EXPORT_BATCH_SIZE", "256")
    config = get_otel_endpoints_base_config()
    assert config["batch_max_queue_size"] == 1024
    assert config["batch_max_export_batch_size"] == 256


# ── get_otel_endpoint_by_agent_info ──────────────────────────────────


@pytest.mark.parametrize(
    "agent_info, expected_len",
    [
        (None, 0),
        ({}, 0),
        ({"otel_info": None}, 0),
        ({"otel_info": {}}, 0),
        ({"otel_info": {"otel_url": "http://host:4317", "otel_token": "tok123"}}, 1),
        ({"otel_info": {"otel_url": "http://host:4317", "otel_token": ""}}, 1),
        ({"otel_info": {"otel_url": "", "otel_token": "tok"}}, 0),
    ],
)
def test_get_otel_endpoint_by_agent_info(agent_info, expected_len):
    result = get_otel_endpoint_by_agent_info(agent_info=agent_info)
    assert isinstance(result, list)
    assert len(result) == expected_len
    if expected_len == 1:
        assert result[0]["url"] == "http://host:4317"
        assert "batch_max_queue_size" in result[0]


# ── get_otel_endpoint_by_json_str ────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """确保每个用例前环境变量干净。"""
    for key in [
        "BKAI_AGENT_OTEL_ENDPOINTS",
        "BKAI_AGENT_OTEL_EXPORTER_TYPE",
        "BKAI_AGENT_APM_OTEL_ENABLED",
        "OTEL_GRPC_URL",
        "OTEL_BK_DATA_TOKEN",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_get_otel_endpoint_by_json_str_empty():
    assert get_otel_endpoint_by_json_str("") == []
    assert get_otel_endpoint_by_json_str("  ") == []
    assert get_otel_endpoint_by_json_str(None) == []


def test_get_otel_endpoint_by_json_str_from_env(monkeypatch):
    monkeypatch.setenv("BKAI_AGENT_OTEL_ENDPOINTS", "http://host1:4317,http://host2:4317")
    result = get_otel_endpoint_by_json_str()
    assert len(result) == 2


def test_get_otel_endpoint_by_json_str_single_url():
    result = get_otel_endpoint_by_json_str("http://host:4317")
    assert len(result) == 1
    assert result[0]["url"] == "http://host:4317"
    assert "batch_max_queue_size" in result[0]


def test_get_otel_endpoint_by_json_str_json_format():
    result = get_otel_endpoint_by_json_str('[{"url": "http://host:4317", "token": "tok"}]')
    assert len(result) == 1
    assert result[0]["url"] == "http://host:4317"
    assert result[0]["token"] == "tok"


# ── get_otel_endpoint_by_env ─────────────────────────────────────────


def test_get_otel_endpoint_by_env_disabled():
    assert get_otel_endpoint_by_env() == []


def test_get_otel_endpoint_by_env_enabled(monkeypatch):
    monkeypatch.setenv("BKAI_AGENT_APM_OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_GRPC_URL", "grpc://otel:4317")
    monkeypatch.setenv("OTEL_BK_DATA_TOKEN", "bktoken")
    result = get_otel_endpoint_by_env()
    assert len(result) == 1
    assert result[0]["url"] == "grpc://otel:4317"
    assert result[0]["exporter_type"].value == "grpc"
    assert "batch_max_queue_size" in result[0]


def test_get_otel_endpoint_by_env_missing_token(monkeypatch):
    monkeypatch.setenv("BKAI_AGENT_APM_OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_GRPC_URL", "grpc://otel:4317")
    assert get_otel_endpoint_by_env() == []


# ── 集成：三个函数组合 ───────────────────────────────────────────────


def test_combined_endpoints(monkeypatch):
    """模拟 apps.py 中 init_bk_aidev_agent_otel 的逻辑"""
    monkeypatch.setenv("BKAI_AGENT_OTEL_ENDPOINTS", "http://host1:4317")
    monkeypatch.setenv("BKAI_AGENT_APM_OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_GRPC_URL", "grpc://otel:4317")
    monkeypatch.setenv("OTEL_BK_DATA_TOKEN", "bktoken")

    agent_info = {"otel_info": {"otel_url": "http://otel:4317", "otel_token": "mytoken"}}

    endpoints = []
    endpoints.extend(get_otel_endpoint_by_json_str())
    endpoints.extend(get_otel_endpoint_by_agent_info(agent_info=agent_info))
    endpoints.extend(get_otel_endpoint_by_env())

    assert len(endpoints) == 3
