# -*- coding: utf-8 -*-
"""AidevAGUIAgent._emit_run_end_extras 协议契约测试。

只覆盖协议层职责：
- 无 hook 时 ``_emit_run_end_extras`` 是空 async generator
- 有 hook 时按顺序转发 hook 产出的事件，并把 ``state_values / thread_id / active_run /
  dispatch_event`` 4 项运行期上下文以关键字参数传给 hook
- 源码级：hook 调用点位于 MESSAGES_SNAPSHOT 之后、RUN_FINISHED 之前

业务契约（PV 判定 / PaaS HTTP / artifact 转换 / 异常兜底）测试见
``tests/services/test_artifacts_hook.py``。
"""

import inspect
from typing import Any
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.agent import LangGraphAGUIAgent


def _make_agent(hook=None) -> AidevAGUIAgent:
    """构造仅用于 hook 单测的 agent 实例（跳过 super().__init__ 昂贵的 graph 初始化）。"""
    agent = AidevAGUIAgent.__new__(AidevAGUIAgent)
    agent._run_end_extras_hook = hook
    agent.active_run = {"id": "run-1", "started_at": None}
    agent._event_handler = None
    return agent


class TestEmitRunEndExtrasProtocol:
    @pytest.mark.asyncio
    async def test_no_hook_is_empty_generator(self):
        agent = _make_agent(hook=None)
        events = [ev async for ev in agent._emit_run_end_extras({}, "sess-1")]
        assert events == []

    @pytest.mark.asyncio
    async def test_hook_events_are_forwarded_in_order(self):
        sentinel_1 = object()
        sentinel_2 = object()

        async def hook(*, state_values, thread_id, active_run, dispatch_event):
            yield sentinel_1
            yield sentinel_2

        agent = _make_agent(hook=hook)
        events = [ev async for ev in agent._emit_run_end_extras({"k": "v"}, "sess-1")]
        assert events == [sentinel_1, sentinel_2]

    @pytest.mark.asyncio
    async def test_hook_receives_runtime_context_kwargs(self):
        captured: dict[str, Any] = {}

        async def hook(*, state_values, thread_id, active_run, dispatch_event):
            captured["state_values"] = state_values
            captured["thread_id"] = thread_id
            captured["active_run"] = active_run
            captured["dispatch_event"] = dispatch_event
            if False:  # pragma: no cover - 使 hook 成为 async generator
                yield

        agent = _make_agent(hook=hook)
        state = {"foo": "bar"}
        # 消费 generator 触发调用
        async for _ in agent._emit_run_end_extras(state, "sess-x"):
            pass

        assert captured["state_values"] is state
        assert captured["thread_id"] == "sess-x"
        assert captured["active_run"] is agent.active_run
        # dispatch_event 必须是 agent 自己的 _dispatch_event（保留 DB + SSE 分发通道由协议层掌控）
        assert captured["dispatch_event"] == agent._dispatch_event


class TestEventOrderInSource:
    """源码级：hook 调用点位于 MESSAGES_SNAPSHOT 之后、RUN_FINISHED 之前。

    父类 :class:`LangGraphAGUIAgent` 的 ``_handle_stream_events`` 里
    ``async for ev in self._emit_run_end_extras(...): yield ev`` 位于 ``final_snapshot_events[1]``
    发射之后、``RunFinishedEvent`` 构造之前，重构后位置不变。
    """

    def test_hook_called_between_snapshot_and_run_finished(self):
        source = inspect.getsource(LangGraphAGUIAgent._handle_stream_events)
        hook_pos = source.find("_emit_run_end_extras")
        snapshot_pos = source.find("final_snapshot_events[1]")
        # 存在多处 RunFinishedEvent（cancelled 与正常终态），hook 应位于终态那次之前
        finished_pos = source.rfind("RunFinishedEvent(")

        assert hook_pos != -1, "hook 未在 _handle_stream_events 中调用"
        assert snapshot_pos != -1, "未找到 MESSAGES_SNAPSHOT 位点"
        assert finished_pos != -1, "未找到 RUN_FINISHED 位点"
        assert snapshot_pos < hook_pos < finished_pos, "hook 顺序错误"
