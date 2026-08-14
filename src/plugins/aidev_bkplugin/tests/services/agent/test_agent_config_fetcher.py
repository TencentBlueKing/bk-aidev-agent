# -*- coding: utf-8 -*-
"""``AgentConfigFetcher`` 请求级缓存契约：

- 同 ``(app_code, version, username)`` 在同请求内只触发一次底层调用；
- 不同 key 各自独立调用底层；
- 缓存命中返回值是深拷贝，调用方 mutation 不影响下次命中；
- ``clear_request_cache`` 后再次调用会重新触发底层。
"""

import copy
from unittest.mock import MagicMock

import pytest
from aidev_bkplugin.services.agent_config import AgentConfigFetcher
from requests.exceptions import RequestException


@pytest.fixture(autouse=True)
def _clear_cache():
    """每个用例前后清理请求级缓存，避免线程复用导致跨用例污染。"""
    AgentConfigFetcher.clear_request_cache()
    yield
    AgentConfigFetcher.clear_request_cache()


@pytest.fixture
def mock_rm(monkeypatch):
    """拦截 ``resource_manager().retrieve_agent_config``，返回可控 dict。"""
    rm = MagicMock()
    rm.retrieve_agent_config.return_value = {
        "agent_type": "common",
        "prompt_setting": {"content": []},
    }
    monkeypatch.setattr(
        "aidev_bkplugin.services.agent_config.resource_manager",
        lambda: rm,
    )
    return rm


@pytest.fixture
def mock_cache(monkeypatch):
    """用 MagicMock 模拟 django cache，避免依赖真实 django settings 缓存后端。"""
    mock_cache = MagicMock()
    mock_cache.get.return_value = None
    monkeypatch.setattr(
        "aidev_bkplugin.services.agent_config._get_django_cache_backend",
        lambda: mock_cache,
    )
    yield mock_cache
    mock_cache.reset_mock()


def test_same_kwargs_calls_backend_once(mock_rm):
    AgentConfigFetcher.get_info(username="alice", version="v1")
    AgentConfigFetcher.get_info(username="alice", version="v1")
    assert mock_rm.retrieve_agent_config.call_count == 1


def test_different_kwargs_call_backend_separately(mock_rm):
    AgentConfigFetcher.get_info(username="alice", version="v1")
    AgentConfigFetcher.get_info(username="bob", version="v1")
    AgentConfigFetcher.get_info(username="alice", version="v2")
    assert mock_rm.retrieve_agent_config.call_count == 3


def test_caller_mutation_does_not_pollute_next_hit(mock_rm):
    """模拟 ``views/agent.py`` 的 ``agent_info.pop("otel_info", ...)`` 场景。"""
    first = AgentConfigFetcher.get_info(username="alice")
    first.pop("agent_type", None)
    first["prompt_setting"]["content"].append({"role": "user", "content": "x"})

    second = AgentConfigFetcher.get_info(username="alice")
    assert second["agent_type"] == "common"
    assert second["prompt_setting"]["content"] == []


def test_clear_request_cache_forces_refetch(mock_rm):
    AgentConfigFetcher.get_info(username="alice")
    AgentConfigFetcher.clear_request_cache()
    AgentConfigFetcher.get_info(username="alice")
    assert mock_rm.retrieve_agent_config.call_count == 2


def test_get_role_info_inherits_cache(mock_rm):
    """``get_role_info`` 内部走 ``get_info``，自然命中同一缓存。"""
    mock_rm.retrieve_agent_config.return_value = {
        "agent_type": "common",
        "prompt_setting": {"content": [{"role": "system", "content": "hi"}]},
    }
    AgentConfigFetcher.get_info(username="alice")
    AgentConfigFetcher.get_role_info(username="alice")
    assert mock_rm.retrieve_agent_config.call_count == 1


# ============================ django cache 兜底分支 ============================


def _encoded_otel_info() -> str:
    """构造带 ``otel_info`` 的原始后端返回值（otel_info 为 base64+json 编码）。"""
    import base64
    import json

    return base64.b64encode(json.dumps({"endpoint": "grpc://otel"}).encode()).decode()


def test_success_writes_django_cache(mock_rm, mock_cache):
    """username=None 拉取成功 → cache.set 以 agent_info:{app_code}:{version} 写入已解码 dict。

    验证 CONTEXT.md「django cache key 设计 / otel_info 写入语义 / 写入条件」：key 不含 username、timeout=1 周、value 的 otel_info 是 dict。
    同时验证 ``allowed_access`` 被剥离：django cache key 不含 username，写入内容也不应含用户维度数据，避免跨用户污染。
    """
    mock_rm.retrieve_agent_config.return_value = {
        "agent_type": "common",
        "prompt_setting": {"content": []},
        "otel_info": _encoded_otel_info(),
        "allowed_access": True,
    }
    result = AgentConfigFetcher.get_info(app_code="app", version="v1")
    assert result["otel_info"] == {"endpoint": "grpc://otel"}
    # 返回给调用方的 dict 仍含 allowed_access（请求级结果不被剥离影响）
    assert result["allowed_access"] is True
    mock_cache.set.assert_called_once()
    key, value, kwargs = mock_cache.set.call_args[0][0], mock_cache.set.call_args[0][1], mock_cache.set.call_args.kwargs
    assert key == "agent_info:app:v1"
    assert isinstance(value["otel_info"], dict)
    assert kwargs.get("timeout") == 7 * 24 * 60 * 60
    # django cache 写入值剥离 allowed_access（用户相关字段不进全局 fallback）
    assert "allowed_access" not in value


def test_success_without_otel_info_skips_django_cache(mock_rm, mock_cache):
    """拉取成功但无 otel_info → 跳过 django cache 写入（otel_info 缺失视为配置异常，不污染 fallback）。"""
    AgentConfigFetcher.get_info(app_code="app", version="v1")
    mock_cache.set.assert_not_called()


def test_failure_empty_username_hits_django_cache(mock_rm, mock_cache):
    """username 为空 + 拉取失败（网络异常）+ cache 命中 → 返回 deepcopy 兜底值，异常被吞（启动可拉起）。"""
    mock_rm.retrieve_agent_config.side_effect = RequestException("backend down")
    mock_cache.get.return_value = {
        "agent_type": "common",
        "prompt_setting": {"content": []},
        "otel_info": {"endpoint": "grpc://otel"},
    }
    result = AgentConfigFetcher.get_info(app_code="app", version="v1")
    mock_cache.get.assert_called_once_with("agent_info:app:v1")
    assert result["agent_type"] == "common"
    assert result["otel_info"] == {"endpoint": "grpc://otel"}


def test_failure_empty_username_no_cache_raises_valueerror(mock_rm, mock_cache):
    """username 为空 + 拉取失败（网络异常）+ cache 未命中 → 抛 ValueError，且 __cause__ 链上原始平台异常。"""
    platform_exc = RequestException("backend down")
    mock_rm.retrieve_agent_config.side_effect = platform_exc
    mock_cache.get.return_value = None
    with pytest.raises(ValueError) as exc_info:
        AgentConfigFetcher.get_info(app_code="app", version="v1")
    # 异常链保留根因：运维可从 __cause__ 判断是超时/鉴权/404
    assert exc_info.value.__cause__ is platform_exc


def test_failure_with_username_re_raises(mock_rm, mock_cache):
    """带 username 拉取失败（网络异常）→ re-raise 原异常，且不读 django cache（不兜底锁定）。"""
    mock_rm.retrieve_agent_config.side_effect = RequestException("backend down")
    with pytest.raises(RequestException):
        AgentConfigFetcher.get_info(app_code="app", version="v1", username="alice")
    mock_cache.get.assert_not_called()


def test_non_network_exception_propagates_without_fallback(mock_rm, mock_cache):
    """非网络异常（如代码 bug、BKAPIError 配置异常）→ 原样冒泡，不进入兜底分支。

    契约：``except RequestException`` 只兜底网络异常；其它异常（``PathParamsMissing`` /
    ``UserNotAuthenticated`` / 编程错误等）不应被吞成"启动可拉起"，否则会掩盖真实问题。
    """
    mock_rm.retrieve_agent_config.side_effect = RuntimeError("not a network error")
    # 无 username 也不兜底——非网络异常直接冒泡
    with pytest.raises(RuntimeError):
        AgentConfigFetcher.get_info(app_code="app", version="v1")
    mock_cache.get.assert_not_called()


def test_django_cache_backend_unavailable_degrades(mock_rm, mock_cache):
    """cache 后端不可用：
    - 读侧（get 抛异常）：抛 RuntimeError + 链上原始平台异常（``__cause__``），不吞成无异常链的 ValueError；
    - 写侧（set 抛异常）：拉取成功分支降级不崩，正常返回。
    """
    platform_exc = RequestException("backend down")
    mock_rm.retrieve_agent_config.side_effect = platform_exc
    mock_cache.get.side_effect = Exception("cache backend down")
    # 拉取失败 + username 为空 + cache 读异常 → RuntimeError，且 __cause__ 是原始平台异常
    with pytest.raises(RuntimeError, match="django cache read error") as exc_info:
        AgentConfigFetcher.get_info(app_code="app", version="v1")
    # 异常链保留根因：原始平台 RequestException 不丢失，运维可区分超时/鉴权/404/缓存故障
    assert exc_info.value.__cause__ is platform_exc

    # 拉取成功 + set 抛异常 → 不崩，正常返回
    mock_rm.retrieve_agent_config.side_effect = None
    mock_rm.retrieve_agent_config.return_value = {
        "agent_type": "common",
        "prompt_setting": {"content": []},
        "otel_info": _encoded_otel_info(),
    }
    mock_cache.set.side_effect = Exception("cache backend down")
    result = AgentConfigFetcher.get_info(app_code="app", version="v1")
    assert result["agent_type"] == "common"


def test_fallback_value_is_deepcopy(mock_rm, mock_cache):
    """兜底命中后 mutation 返回 dict，二次调用（再次兜底）不受污染（deepcopy 语义）。"""
    mock_rm.retrieve_agent_config.side_effect = RequestException("backend down")
    mock_cache.get.return_value = {
        "agent_type": "common",
        "prompt_setting": {"content": []},
    }
    first = AgentConfigFetcher.get_info(app_code="app", version="v1")
    first.pop("agent_type", None)
    first["prompt_setting"]["content"].append({"role": "user", "content": "x"})

    second = AgentConfigFetcher.get_info(app_code="app", version="v1")
    assert second["agent_type"] == "common"
    assert second["prompt_setting"]["content"] == []


# ============================ 跨用户隔离契约 ============================


def test_user_request_strips_allowed_access_from_django_cache(mock_rm, mock_cache):
    """带 username 拉取成功 → 返回值含调用方的 ``allowed_access``，但 django cache 写入值剥离之。

    CR 场景：任意用户请求都可能把完整响应覆盖到全局 fallback key（key 不含 username）。
    修复后写入内容剥离 ``allowed_access``，调用方拿到的原始结果不受影响。
    """
    mock_rm.retrieve_agent_config.return_value = {
        "agent_type": "common",
        "prompt_setting": {"content": []},
        "otel_info": _encoded_otel_info(),
        "allowed_access": True,
    }
    result = AgentConfigFetcher.get_info(app_code="app", version="v1", username="alice")
    # 调用方拿到的仍是原始结果（请求级结果不被剥离影响）
    assert result["allowed_access"] is True
    # django cache 写入值剥离 allowed_access
    mock_cache.set.assert_called_once()
    value = mock_cache.set.call_args[0][1]
    assert "allowed_access" not in value
    assert isinstance(value["otel_info"], dict)


def test_alice_bob_no_username_isolation(mock_rm, mock_cache):
    """Alice / Bob / 无用户三方隔离。

    场景构造（CR 描述的跨上下文污染路径）：
    1. Bob（allowed_access=True）先拉取成功 → 写全局 fallback（剥离后无 allowed_access）；
    2. Alice 拉取失败 → re-raise，不读 django cache（带 username 失败不兜底）；
    3. 无用户拉取失败 → 读全局 fallback 兜底 → 不含 Bob 的 allowed_access。

    关键断言：无用户兜底命中的 dict **不含** ``allowed_access``，即不会被 Bob 的权限串扰；
    ``permissions.py:31`` 走 ``.get("allowed_access", False)`` 安全降级为拒绝。
    """
    # Bob 拉取成功，写 fallback（剥离 allowed_access）
    bob_payload = {
        "agent_type": "common",
        "prompt_setting": {"content": []},
        "otel_info": _encoded_otel_info(),
        "allowed_access": True,
    }
    mock_rm.retrieve_agent_config.return_value = bob_payload
    bob_result = AgentConfigFetcher.get_info(app_code="app", version="v1", username="bob")
    assert bob_result["allowed_access"] is True
    # django cache 写入值不含 allowed_access
    fallback_written = mock_cache.set.call_args[0][1]
    assert "allowed_access" not in fallback_written

    # 模拟 cache 命中：返回的就是 Bob 写入的 fallback 投影（剥离后）
    mock_cache.get.return_value = copy.deepcopy(fallback_written)

    # Alice 拉取失败（网络异常）→ re-raise，且不读 django cache（带 username 失败不兜底）
    mock_rm.retrieve_agent_config.side_effect = RequestException("backend down")
    mock_cache.get.reset_mock()
    with pytest.raises(RequestException):
        AgentConfigFetcher.get_info(app_code="app", version="v1", username="alice")
    mock_cache.get.assert_not_called()

    # 无用户拉取失败 → 读 fallback 兜底 → 不含 allowed_access
    mock_cache.get.reset_mock()
    no_user_result = AgentConfigFetcher.get_info(app_code="app", version="v1")
    mock_cache.get.assert_called_once_with("agent_info:app:v1")
    # 关键：兜底返回的 dict 不含 allowed_access，permissions 层 .get(..., False) → 拒绝
    assert "allowed_access" not in no_user_result
    assert no_user_result.get("allowed_access", False) is False
    # otel_info 仍可用（启动场景 OTel 初始化所需）
    assert isinstance(no_user_result["otel_info"], dict)
