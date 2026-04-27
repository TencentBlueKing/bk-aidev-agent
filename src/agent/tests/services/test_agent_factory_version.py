# -*- coding: utf-8 -*-
"""AgentInstanceFactory 的 version 路由单元测试。

验证：
- ``__init__/build_agent`` 接受 ``version`` 形参；
- ``get_agent_config(agent_code)`` 对**主 agent_code** 透传 ``self.version``；
- 对**子 agent_code``（命令切换出去的 mapping 目标）一律传 ``None``（最新版），
  不继承父 ``version``，符合"子 agent 版本语义独立"的设计约束。

注：``AgentInstanceFactory`` 构造受私有 ``_FACTORY_TOKEN`` 闸口保护；同包单元测试
作为"知情人"显式传入该凭证以构造工厂实例，外部代码必须走 ``build_agent``。
"""

from unittest.mock import MagicMock

import pytest
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.agent.factory import _FACTORY_TOKEN


class _FakeConfigManager:
    """模拟 AgentConfigManager，用 MagicMock 接管 ``get_config`` 以便断言入参。"""

    get_config = MagicMock()


def _build_factory(version=None):
    _FakeConfigManager.get_config.reset_mock()
    return AgentInstanceFactory(
        agent_code="main_agent",
        resource_manager=MagicMock(),
        config_manager_class=_FakeConfigManager,
        version=version,
        _token=_FACTORY_TOKEN,
    )


def test_version_passes_through_for_main_agent_code():
    factory = _build_factory(version="v2")
    factory.get_agent_config("main_agent")
    _FakeConfigManager.get_config.assert_called_once_with(
        agent_code="main_agent",
        resource_manager=factory.resource_manager,
        version="v2",
    )


def test_version_not_inherited_by_sub_agent_code():
    """子 agent_code 必须走 None（最新版），不继承父 version。"""
    factory = _build_factory(version="v2")
    factory.get_agent_config("sub_agent_code")
    _FakeConfigManager.get_config.assert_called_once_with(
        agent_code="sub_agent_code",
        resource_manager=factory.resource_manager,
        version=None,
    )


def test_no_version_means_latest_for_all():
    """未传 version 时，主/子 agent 都走 latest（与历史行为一致）。"""
    factory = _build_factory(version=None)
    factory.get_agent_config("main_agent")
    factory.get_agent_config("sub_agent_code")
    assert _FakeConfigManager.get_config.call_count == 2
    for call in _FakeConfigManager.get_config.call_args_list:
        assert call.kwargs["version"] is None


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
