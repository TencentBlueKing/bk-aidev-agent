# -*- coding: utf-8 -*-
"""模型点位测试：model_pre 每次调用前、model_post 每次调用后（含中间响应）。"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from aidev_agent.core.hook import HookAbort, HookPoint, HookRetry, HookSet

from .conftest import make_config, run_node

TOOL_CALL_RESPONSE = AIMessage(
    content="",
    tool_calls=[{"name": "search", "args": {"query": "x"}, "id": "call-1"}],
)


def test_model_pre_replace_becomes_actual_request(fake_llm, build_model_node_with_hooks) -> None:
    """model_pre 返回的新列表与实际发送给模型的消息逐项相同。"""
    replacement = [SystemMessage(content="SYS"), HumanMessage(content="REPLACED")]
    hooks = HookSet({HookPoint.MODEL_PRE: [lambda context: replacement]})
    llm = fake_llm([AIMessage(content="final")])
    node = build_model_node_with_hooks(llm, hooks=hooks)

    run_node(node, make_config())

    assert [item.content for item in llm.calls[0]] == ["SYS", "REPLACED"]


def test_model_pre_runs_on_every_model_call(fake_llm, build_model_node_with_hooks) -> None:
    """每次模型链调用前都触发 model_pre，工具调用后的重新请求也不例外。"""
    seen: list[str] = []
    hooks = HookSet({HookPoint.MODEL_PRE: [lambda context: seen.append("pre")]})
    llm = fake_llm([TOOL_CALL_RESPONSE, AIMessage(content="final")])
    node = build_model_node_with_hooks(llm, hooks=hooks)
    config = make_config()

    run_node(node, config)
    run_node(node, config)

    assert seen == ["pre", "pre"]


def test_model_post_sees_intermediate_tool_call_response(fake_llm, build_model_node_with_hooks) -> None:
    """model_post 每次模型调用成功后触发，带 tool_calls 的中间响应也会进入处理器。"""
    seen: list[AIMessage] = []
    hooks = HookSet({HookPoint.MODEL_POST: [lambda context: seen.append(context.payload.response)]})
    llm = fake_llm([TOOL_CALL_RESPONSE, AIMessage(content="final")])
    node = build_model_node_with_hooks(llm, hooks=hooks)
    config = make_config()

    run_node(node, config)
    run_node(node, config)

    assert [bool(message.tool_calls) for message in seen] == [True, False]
    assert seen[-1].content == "final"


def test_model_post_replace_becomes_output(fake_llm, build_model_node_with_hooks) -> None:
    """model_post 返回新 AIMessage 即替换本轮输出。"""
    hooks = HookSet(
        {HookPoint.MODEL_POST: [lambda context: context.payload.response.model_copy(update={"content": "FIXED"})]}
    )
    llm = fake_llm([AIMessage(content="final")])
    node = build_model_node_with_hooks(llm, hooks=hooks)

    result = run_node(node, make_config())

    assert result["messages"][0].content == "FIXED"


def test_hook_retry_calls_model_again(fake_llm, build_model_node_with_hooks) -> None:
    """model_post 抛 HookRetry 时模型被重新调用，重试成功后正常返回。"""

    def retry_once(context):
        if context.payload.response.content == "bad":
            raise HookRetry("answer again")

    hooks = HookSet({HookPoint.MODEL_POST: [retry_once]})
    llm = fake_llm([AIMessage(content="bad"), AIMessage(content="good")])
    node = build_model_node_with_hooks(llm, hooks=hooks)

    result = run_node(node, make_config())

    assert len(llm.calls) == 2
    assert result["messages"][0].content == "good"


def test_model_post_abort_terminates_run(fake_llm, build_model_node_with_hooks) -> None:
    """model_post 抛 HookAbort 时本轮以可读错误终止。"""

    def abort(context):
        raise HookAbort(HookPoint.MODEL_POST, "rejected")

    hooks = HookSet({HookPoint.MODEL_POST: [abort]})
    llm = fake_llm([AIMessage(content="final")])
    node = build_model_node_with_hooks(llm, hooks=hooks)

    with pytest.raises(HookAbort, match="rejected"):
        run_node(node, make_config())


def test_model_pre_abort_blocks_request(fake_llm, build_model_node_with_hooks) -> None:
    """model_pre 抛 HookAbort 时不发起模型请求。"""

    def abort(context):
        raise HookAbort(HookPoint.MODEL_PRE, "blocked")

    hooks = HookSet({HookPoint.MODEL_PRE: [abort]})
    llm = fake_llm([AIMessage(content="final")])
    node = build_model_node_with_hooks(llm, hooks=hooks)

    with pytest.raises(HookAbort):
        run_node(node, make_config())

    assert llm.calls == []


def test_model_hooks_can_mutate_ctx_in_place(fake_llm, build_model_node_with_hooks) -> None:
    """处理器直接改 ctx 与返回新对象等价。"""

    def pre(context):
        context.payload.messages = context.payload.messages + [SystemMessage(content="INJECTED")]

    def post(context):
        context.payload.response.content = "IN-PLACE"

    hooks = HookSet({HookPoint.MODEL_PRE: [pre], HookPoint.MODEL_POST: [post]})
    llm = fake_llm([AIMessage(content="final")])
    node = build_model_node_with_hooks(llm, hooks=hooks)

    result = run_node(node, make_config())

    assert [message.content for message in llm.calls[0]] == ["hello", "INJECTED"]
    assert result["messages"][0].content == "IN-PLACE"


def test_model_hooks_work_in_async_invocation(fake_llm, build_model_node_with_hooks) -> None:
    """异步调用路径同样触发 model_pre / model_post。"""
    import asyncio
    from unittest.mock import Mock

    seen: list[str] = []
    hooks = HookSet(
        {
            HookPoint.MODEL_PRE: [lambda context: seen.append("pre")],
            HookPoint.MODEL_POST: [lambda context: seen.append("post")],
        }
    )
    llm = fake_llm([AIMessage(content="final")])
    node = build_model_node_with_hooks(llm, hooks=hooks)

    result = asyncio.run(
        node.ainvoke({"messages": [HumanMessage(content="hello")]}, config=make_config(), store=Mock())
    )

    assert seen == ["pre", "post"]
    assert result["messages"][0].content == "final"
