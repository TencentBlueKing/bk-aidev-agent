# -*- coding: utf-8 -*-
"""AgentInstanceFactory 的 version 路由单元测试。

验证：
- ``__init__/build_agent`` 接受 ``version`` 形参；
- ``get_agent_config(agent_code)`` 对**主 agent_code** 透传 ``self.version``；
- 对**子 agent_code**（命令切换出去的 mapping 目标）一律传 ``None``（最新版），
  不继承父 ``version``，符合"子 agent 版本语义独立"的设计约束。

注：``AgentInstanceFactory`` 构造受私有 ``_FACTORY_TOKEN`` 闸口保护；同包单元测试
作为"知情人"显式传入该凭证以构造工厂实例，外部代码必须走 ``build_agent``。
"""

from unittest.mock import MagicMock

import pytest
from aidev_agent.pydantic_models import AgentConfig, AgentOptions
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.agent.factory import _FACTORY_TOKEN


def _make_resource_manager() -> MagicMock:
    """显式注入到 factory 的资源管理器 Mock；只关注 ``get_agent_config`` 的入参语义。"""
    rm = MagicMock(name="resource_manager")
    rm.get_agent_config = MagicMock(name="get_agent_config")
    return rm


def _build_factory(version=None) -> AgentInstanceFactory:
    return AgentInstanceFactory(
        agent_code="main_agent",
        resource_manager=_make_resource_manager(),
        version=version,
        _token=_FACTORY_TOKEN,
    )


def _make_agent_config() -> AgentConfig:
    return AgentConfig(
        agent_code="main_agent",
        agent_name="origin",
        chat_model="test-model",
        non_thinking_llm="test-non-thinking",
        fast_llm="test-non-thinking",
        agent_options=AgentOptions(),
    )


def test_version_passes_through_for_main_agent_code():
    factory = _build_factory(version="v2")
    factory.get_agent_config("main_agent")
    factory.resource_manager.get_agent_config.assert_called_once_with(agent_code="main_agent", version="v2")


def test_version_not_inherited_by_sub_agent_code():
    """子 agent_code 必须走 None（最新版），不继承父 version。"""
    factory = _build_factory(version="v2")
    factory.get_agent_config("sub_agent_code")
    factory.resource_manager.get_agent_config.assert_called_once_with(agent_code="sub_agent_code", version=None)


def test_no_version_means_latest_for_all():
    """未传 version 时，主/子 agent 都走 latest（与历史行为一致）。"""
    factory = _build_factory(version=None)
    factory.get_agent_config("main_agent")
    factory.get_agent_config("sub_agent_code")
    assert factory.resource_manager.get_agent_config.call_count == 2
    for call in factory.resource_manager.get_agent_config.call_args_list:
        assert call.kwargs["version"] is None


def test_same_agent_code_fetched_once_per_build_with_independent_copies():
    factory = _build_factory(version="v2")
    factory.resource_manager.get_agent_config.return_value = _make_agent_config()

    first = factory.get_agent_config("main_agent")
    first.agent_name = "changed"
    second = factory.get_agent_config("main_agent")

    factory.resource_manager.get_agent_config.assert_called_once_with(agent_code="main_agent", version="v2")
    assert second.agent_name == "origin"


def test_init_stores_version_attr():
    """version 必须被存到 self.version 上，供下游 builder 读取。"""
    factory = _build_factory(version="v3")
    assert factory.version == "v3"
    factory_no_ver = _build_factory(version=None)
    assert factory_no_ver.version is None


def test_direct_init_without_token_raises():
    """对外 API 约束：直接 ``AgentInstanceFactory(...)`` 应当 raise，必须走 ``build_agent``。"""
    with pytest.raises(RuntimeError, match="build_agent"):
        AgentInstanceFactory(agent_code="main_agent")


def test_direct_init_with_wrong_token_raises():
    """传错 token 也必须拒绝，避免外部猜中 keyword 名绕过。"""
    with pytest.raises(RuntimeError, match="build_agent"):
        AgentInstanceFactory(agent_code="main_agent", _token=object())
