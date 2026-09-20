# -*- coding: utf-8 -*-
"""``ChatAgentBuilder.build_chat_model_vision`` 的配置读取与三态行为。

模型名来源为平台下发的 ``agent_info["prompt_setting"]["fallback_vision_model"]``：
有值 → 构造视觉模型实例；缺失 / ``None`` / 空串 → 返回 ``None``（三态同义为未配置）。
"""

from unittest.mock import MagicMock

import pytest
from aidev_agent.services.agent.chat import ChatAgentBuilder


def _builder(agent_info, *, session_code=None, endpoint="https://gw.example.com/v1", monkeypatch=None):
    """构造仅暴露 agent_info / chat / session_code 的 ChatAgentBuilder。"""
    ctx = MagicMock()
    ctx.agent_config.agent_info = agent_info
    ctx.session_code = session_code
    ctx.chat = None
    monkeypatch.setattr("aidev_agent.services.agent.chat.settings.LLM_GW_ENDPOINT", endpoint, raising=False)
    return ChatAgentBuilder(ctx)


@pytest.mark.parametrize(
    "agent_info, expect_none",
    [
        ({"prompt_setting": {"fallback_vision_model": "gpt-4o-mini"}}, False),
        ({"prompt_setting": {"fallback_vision_model": None}}, True),
        ({"prompt_setting": {"fallback_vision_model": ""}}, True),
        ({"prompt_setting": {}}, True),
        ({"prompt_setting": None}, True),
        ({}, True),
        (None, True),
    ],
)
def test_build_chat_model_vision_states(agent_info, expect_none, monkeypatch):
    """视觉模型名缺失 / None / 空串 / agent_info 缺失 → 均返回 None（不抛异常）。"""
    sentinel = MagicMock()
    monkeypatch.setattr(
        "aidev_agent.services.agent.chat.ChatModel.get_setup_instance",
        lambda **kw: sentinel,
    )
    builder = _builder(agent_info, monkeypatch=monkeypatch)
    result = builder.build_chat_model_vision()
    assert (result is None) is expect_none


def test_build_chat_model_vision_passes_model_name(monkeypatch):
    """模型名经 kwargs["model"] 传入，且不得携带 fallback_model。"""
    captured: dict = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("aidev_agent.services.agent.chat.ChatModel.get_setup_instance", _capture)
    builder = _builder({"prompt_setting": {"fallback_vision_model": "gpt-4o-mini"}}, monkeypatch=monkeypatch)
    builder.build_chat_model_vision()

    assert captured["model"] == "gpt-4o-mini"
    assert "fallback_model" not in captured


@pytest.mark.parametrize("endpoint", ["", None])
def test_build_chat_model_vision_empty_endpoint_still_builds(endpoint, monkeypatch):
    """网关端点为空/None 时不再视为未配置，仍构造实例并原样透传 base_url。"""
    captured: dict = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("aidev_agent.services.agent.chat.ChatModel.get_setup_instance", _capture)
    builder = _builder(
        {"prompt_setting": {"fallback_vision_model": "gpt-4o-mini"}},
        endpoint=endpoint,
        monkeypatch=monkeypatch,
    )
    assert builder.build_chat_model_vision() is not None

    assert "base_url" in captured
    assert captured["base_url"] == endpoint
    assert captured["model"] == "gpt-4o-mini"


def test_build_chat_model_vision_passes_session_code(monkeypatch):
    """会话标识透传至模型工厂，使视觉调用纳入会话归属。"""
    captured: dict = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("aidev_agent.services.agent.chat.ChatModel.get_setup_instance", _capture)
    builder = _builder(
        {"prompt_setting": {"fallback_vision_model": "gpt-4o-mini"}},
        session_code="s-1",
        monkeypatch=monkeypatch,
    )
    builder.build_chat_model_vision()

    assert captured["session_code"] == "s-1"
