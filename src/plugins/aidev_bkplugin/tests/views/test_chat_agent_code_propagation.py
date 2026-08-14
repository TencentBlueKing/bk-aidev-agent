# -*- coding: utf-8 -*-
"""``ChatCompletionViewSet.create`` → serializer 的 agent_code 传递契约。

``agent_type`` 由 serializer 内部经 ``AgentConfigFetcher.get_info`` 决定，而 get_info 的
``app_code`` 缺省会回落到全局 resource manager（主智能体）。因此 view 必须把请求级
``rm.get_agent_code()`` 经 context 传下去，否则 rm 指向 flow 型子智能体、主智能体为 chat 时，
路由会按主智能体的 agent_type 走进错误的构建分支。

serializer 侧的取值断言见 tests/views/test_chat_completion_serializer.py，
本文件专门守护 view → serializer 这一段传递。
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_bk_plugin_framework = MagicMock()
_bk_plugin_framework.kit.decorators.inject_user_token = lambda func: func
sys.modules.setdefault("bk_plugin_framework", _bk_plugin_framework)
sys.modules.setdefault("bk_plugin_framework.kit", _bk_plugin_framework.kit)
sys.modules.setdefault("bk_plugin_framework.kit.decorators", _bk_plugin_framework.kit.decorators)


def test_create_passes_request_scoped_agent_code_to_serializer(monkeypatch):
    from aidev_bkplugin.views import chat as mod

    captured = {}

    class _CapturingSerializer:
        """捕获 context 后立即中断，避免把 create 后续的装配链路拖进来。"""

        def __init__(self, data=None, context=None):
            captured["context"] = context

        def is_valid(self, raise_exception=False):
            raise RuntimeError("stop-after-context-capture")

    monkeypatch.setattr(mod, "ChatCompletionRequestSerializer", _CapturingSerializer)

    rm = MagicMock()
    rm.get_agent_code.return_value = "sub-agent"
    view = mod.ChatCompletionViewSet()
    # raising=False：其它用例会把 views.base 换成假模块（PluginViewSet = object），
    # 此时基类方法并不存在，不能要求属性预先有定义。
    monkeypatch.setattr(view, "get_username", lambda: "alice", raising=False)
    monkeypatch.setattr(view, "get_resource_manager", lambda: rm, raising=False)

    request = SimpleNamespace(data={"input": "hi"}, user=SimpleNamespace(username="alice"))
    # create 捕获内部异常后统一转抛 ClientBlueException；session_code 为空，不会触发错误写库分支
    with pytest.raises(Exception):
        view.create(request)

    assert captured["context"] == {"username": "alice", "agent_code": "sub-agent"}
