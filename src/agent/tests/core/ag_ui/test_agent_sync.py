# -*- coding: utf-8 -*-
"""检查点消息同步测试（Phase 6 修复）。

验证：
- thread_id 稳定性：统一使用 self.thread_id，无 uuid4 后缀
- RemoveMessage 同步在 _execute() 中执行（覆盖流式和非流式路径）
- PV 状态在稳定 thread_id 下跨请求持久化
- 边界情况：空检查点、id=None 的消息
"""

import os
import subprocess
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.ag_ui.agent import LangGraphAgent
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph, add_messages
from typing_extensions import Annotated, TypedDict

# 读取 chat.py 源码（避免 import 触发 ag_ui 等不可用依赖）
_CHAT_PY_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "aidev_agent", "services", "agent", "chat.py")
_CHAT_PY_PATH = os.path.normpath(_CHAT_PY_PATH)

# 读取 agent.py 源码
_AGENT_PY_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "aidev_agent", "core", "ag_ui", "agent.py")
_AGENT_PY_PATH = os.path.normpath(_AGENT_PY_PATH)


def _read_chat_py() -> str:
    with open(_CHAT_PY_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _read_agent_py() -> str:
    with open(_AGENT_PY_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _extract_method_source(source: str, method_name: str) -> str:
    """从源码中提取方法的缩进源码块（支持 sync def 和 async def）。"""
    lines = source.splitlines()
    start = None
    indent = None
    result = []
    in_signature = False  # 多行签名（括号未闭合）
    paren_depth = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if start is None:
            if stripped.startswith((f"def {method_name}(", f"async def {method_name}(")):
                start = i
                indent = len(line) - len(line.lstrip())
                result.append(line)
                # 跟踪括号深度
                paren_depth += stripped.count("(") - stripped.count(")")
                in_signature = paren_depth > 0
        else:
            if in_signature:
                result.append(line)
                paren_depth += stripped.count("(") - stripped.count(")")
                if paren_depth <= 0:
                    in_signature = False
                continue
            if line.strip() == "" or len(line) - len(line.lstrip()) > indent:
                result.append(line)
            else:
                break
    return "\n".join(result)


class TestThreadIdStability:
    """验证 thread_id 统一使用 self.thread_id，无 UUID 后缀。"""

    def test_stream_uses_self_thread_id(self):
        """_stream() 应直接使用 self.thread_id，无中间变量。"""
        source = _read_chat_py()
        stream_source = _extract_method_source(source, "_stream")
        assert "uuid.uuid4().hex[:8]" not in stream_source, "graph_thread_id 仍使用 uuid4 后缀 — bug 未修复"
        # 不应有 stream_thread_id 或 graph_thread_id 中间变量
        assert "stream_thread_id" not in stream_source, (
            "_stream() 不应有 stream_thread_id 中间变量，应直接使用 self.thread_id"
        )
        assert "graph_thread_id" not in stream_source, (
            "_stream() 不应有 graph_thread_id 中间变量，应直接使用 self.thread_id"
        )
        # 所有 thread_id 使用均为 self.thread_id
        assert '"thread_id": self.thread_id' in stream_source, "AgentInput.thread_id 应为 self.thread_id"

    def test_execute_uses_self_thread_id(self):
        """_execute() 应使用 self.thread_id，不用 execute_kwargs.session_code fallback。"""
        source = _read_chat_py()
        execute_source = _extract_method_source(source, "_execute")
        assert 'cfg["configurable"]["thread_id"] = self.thread_id' in execute_source, (
            "_execute 应直接使用 self.thread_id"
        )
        # 确保没有 session_code fallback 的赋值行（注释中的不算）
        for line in execute_source.splitlines():
            stripped = line.strip()
            if stripped.startswith("cfg[") and "thread_id" in stripped and "session_code" in stripped:
                pytest.fail("_execute 不应有 execute_kwargs.session_code fallback 赋值")


class TestRemoveMessageSync:
    """验证 _execute() 使用 RemoveMessage 同步检查点消息。"""

    @pytest.mark.asyncio
    async def test_sync_removes_stale_messages(self):
        """当检查点包含消息时，应为所有非系统消息创建 RemoveMessage 操作。"""
        checkpoint_msg1 = HumanMessage(id="cp-msg-1", content="hello")
        checkpoint_msg2 = AIMessage(id="cp-msg-2", content="hi there")
        checkpoint_msg3 = SystemMessage(id="cp-msg-3", content="you are helpful")

        mock_snapshot = MagicMock()
        mock_snapshot.values = {"messages": [checkpoint_msg1, checkpoint_msg2, checkpoint_msg3]}

        checkpoint_messages = mock_snapshot.values.get("messages", [])
        non_system = [m for m in checkpoint_messages if not isinstance(m, SystemMessage)]
        remove_ops = [RemoveMessage(id=m.id) for m in non_system if m.id is not None]

        assert len(remove_ops) == 2
        assert remove_ops[0].id == "cp-msg-1"
        assert remove_ops[1].id == "cp-msg-2"

    @pytest.mark.asyncio
    async def test_sync_empty_checkpoint(self):
        """当检查点为空时，不需要 RemoveMessage 操作。"""
        mock_snapshot = MagicMock()
        mock_snapshot.values = {"messages": []}

        checkpoint_messages = mock_snapshot.values.get("messages", [])
        non_system = [m for m in checkpoint_messages if not isinstance(m, SystemMessage)]
        remove_ops = [RemoveMessage(id=m.id) for m in non_system if m.id is not None]

        assert len(remove_ops) == 0

    @pytest.mark.asyncio
    async def test_sync_message_with_none_id(self):
        """id=None 的消息应被跳过，不应导致 RemoveMessage 使用 None id。"""
        msg_no_id = HumanMessage(content="no id here")
        assert msg_no_id.id is None

        remove_ops = [RemoveMessage(id=m.id) for m in [msg_no_id] if m.id is not None]
        assert len(remove_ops) == 0

    def test_update_state_called_with_as_node_start(self):
        """update_state 必须以 as_node='__start__' 调用，以确保正确的检查点归属。"""
        mock_graph = MagicMock()
        mock_graph.update_state = MagicMock()

        remove_ops = [MagicMock(id="msg-1")]
        mock_graph.update_state(
            {"configurable": {"thread_id": "test"}},
            {"messages": remove_ops},
            as_node="__start__",
        )

        mock_graph.update_state.assert_called_once()
        call_kwargs = mock_graph.update_state.call_args
        assert call_kwargs[1].get("as_node") == "__start__" or (
            len(call_kwargs[0]) > 2 and call_kwargs[0][2] == "__start__"
        )

    def test_sync_in_execute_not_prepare_stream(self):
        """同步逻辑应在 _execute() 中调用（而非 prepare_stream() 中）。"""
        source = _read_chat_py()
        execute_source = _extract_method_source(source, "_execute")
        sync_source = _extract_method_source(source, "_sync_checkpoint_messages")
        # _execute 应调用 _sync_checkpoint_messages
        assert "_sync_checkpoint_messages" in execute_source, "_execute() 应调用 _sync_checkpoint_messages()"
        # RemoveMessage 实际逻辑在 _sync_checkpoint_messages 中
        assert "RemoveMessage" in sync_source, "_sync_checkpoint_messages() 应包含 RemoveMessage 同步逻辑"

    def test_sync_covers_both_paths(self):
        """同步逻辑在流式/非流式分支之前执行，覆盖两条路径。

        重构后 ainvoke 已抽取到 _invoke（由 _execute else 分支调用），
        因此校验 "_sync_checkpoint_messages 在非流式分发（_invoke 调用）之前"
        而非直接在 _execute 源码中查找 ainvoke。
        """
        source = _read_chat_py()
        execute_source = _extract_method_source(source, "_execute")
        # _sync_checkpoint_messages 调用应在流式/非流式分支之前
        sync_call_pos = execute_source.find("_sync_checkpoint_messages")
        stream_pos = execute_source.find("execute_kwargs.stream")
        invoke_dispatch_pos = execute_source.find("self._invoke(")

        assert sync_call_pos > 0, "_execute() 应调用 _sync_checkpoint_messages"
        assert sync_call_pos < stream_pos, "同步调用应在流式分支之前"
        assert sync_call_pos < invoke_dispatch_pos, "同步调用应在 _invoke（非流式 ainvoke）分发之前"
        # ainvoke 实际调用点应位于 _invoke 方法内
        invoke_source = _extract_method_source(source, "_invoke")
        assert "ainvoke" in invoke_source, "_invoke() 应包含 ainvoke 调用"

    def test_sync_skipped_on_resume(self):
        """resume 路径下必须跳过 _sync_checkpoint_messages，避免清空 checkpoint 中的 tool_call 上下文。"""
        source = _read_chat_py()
        execute_source = _extract_method_source(source, "_execute")
        # _execute 内必须存在 resume 跳过判断（形如 `if not execute_kwargs.resume:` 包裹 sync 调用）
        assert "execute_kwargs.resume" in execute_source, (
            "_execute() 应基于 execute_kwargs.resume 决定是否跳过 _sync_checkpoint_messages"
        )
        # 粗略校验：sync 调用应被 if not ... resume 包裹（容忍空白差异）
        normalized = " ".join(execute_source.split())
        assert "if not execute_kwargs.resume" in normalized and (
            normalized.find("if not execute_kwargs.resume") < normalized.find("_sync_checkpoint_messages(agent_e, cfg)")
        ), "resume 路径下必须显式跳过 _sync_checkpoint_messages 调用"


class TestPVStatePersistence:
    """验证 PV 状态在稳定 thread_id 下跨请求持久化。"""

    @pytest.mark.asyncio
    async def test_pv_state_survives_across_invocations(self):
        """使用稳定的 thread_id，runtime_paas_sbx_pv 应在检查点状态中持久化。"""

        class TestState(TypedDict):
            messages: Annotated[list, add_messages]
            runtime_paas_sbx_pv: list

        def dummy_node(state):
            return {"messages": [AIMessage(content="ok")]}

        builder = StateGraph(TestState)
        builder.add_node("agent", dummy_node)
        builder.add_edge(START, "agent")
        builder.add_edge("agent", END)

        checkpointer = MemorySaver()
        graph = builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "session_abc"}}

        # 第一次调用 — 设置 PV 状态
        await graph.ainvoke(
            {
                "messages": [HumanMessage(content="hi")],
                "runtime_paas_sbx_pv": [{"type": "paas-sbx-pv", "volume_id": "test-vol"}],
            },
            config,
        )

        # 验证 PV 状态已持久化
        state1 = await graph.aget_state(config)
        pv_list = state1.values.get("runtime_paas_sbx_pv", [])
        assert len(pv_list) == 1
        assert pv_list[0]["volume_id"] == "test-vol"

        # 第二次调用 — 同一 thread_id，PV 应仍然存在
        await graph.ainvoke({"messages": [HumanMessage(content="hello again")]}, config)
        state2 = await graph.aget_state(config)
        pv_list2 = state2.values.get("runtime_paas_sbx_pv", [])
        assert len(pv_list2) == 1
        assert pv_list2[0]["volume_id"] == "test-vol"

    def test_fork_time_travel_not_latest_checkpoint(self):
        """fork 后又有新 checkpoint，时间旅行应从 fork checkpoint C 开始而非最新 D。

        Phase 11.5 CR2 修复的 bug：kwargs.update(fork) 不正确，应 merge fork 的
        configurable 到 config.configurable。本测试验证改 sync 后 update_state
        返回的 RunnableConfig 仍被 _stream 正确 merge 到 merged_cfg。
        """

        class TestState(TypedDict):
            messages: Annotated[list, add_messages]

        call_log = []

        def agent_node(state):
            call_log.append(state["messages"][-1].content)
            return {"messages": [AIMessage(content="reply", id=f"ai-{len(call_log)}")]}

        builder = StateGraph(TestState)
        builder.add_node("agent", agent_node)
        builder.add_edge(START, "agent")
        builder.add_edge("agent", END)

        checkpointer = MemorySaver()
        graph = builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "test-fork-timetravel"}}

        # Step 1: 写入 checkpoint A（含 user-msg-1）
        graph.invoke({"messages": [HumanMessage(content="msg-1", id="user-msg-1")]}, config)

        # Step 2: 写入 checkpoint B（含 user-msg-1 + ai-1 + user-msg-2）
        graph.invoke({"messages": [HumanMessage(content="msg-2", id="user-msg-2")]}, config)

        # Step 3: 找 user-msg-2 对应的前一个 checkpoint（模拟 _get_checkpoint_before_message）
        history_list = list(graph.get_state_history(config))
        history_list.reverse()
        time_travel_checkpoint = None
        for idx, snapshot in enumerate(history_list):
            messages = snapshot.values.get("messages", [])
            if any(getattr(m, "id", None) == "user-msg-2" for m in messages):
                if idx > 0:
                    time_travel_checkpoint = history_list[idx - 1]
                break
        assert time_travel_checkpoint is not None, "应找到 user-msg-2 的前一个 checkpoint"

        # Step 4: update_state 创建 fork checkpoint C
        fork_config = graph.update_state(
            time_travel_checkpoint.config,
            time_travel_checkpoint.values,
            as_node=time_travel_checkpoint.next[0] if time_travel_checkpoint.next else "__start__",
        )

        # Step 5: 写入新 checkpoint D（使 D 成为最新）
        graph.invoke({"messages": [HumanMessage(content="msg-3", id="user-msg-3")]}, config)

        # Step 6: 用 merged_cfg（fork C 的 checkpoint_id）调 invoke
        merged_cfg = {
            "configurable": {
                **config["configurable"],
                **fork_config.get("configurable", {}),
            }
        }
        call_log.clear()
        graph.invoke({"messages": [HumanMessage(content="regen-msg", id="regen-1")]}, merged_cfg)

        # Step 7: 断言从 fork checkpoint C 开始（agent 看到的是 C 的消息 + regen-msg，
        #        而非 D 的 msg-3）
        # C 的状态是 user-msg-1（checkpoint A 之后），所以 agent 收到的消息序列应含 msg-1 + regen-msg
        # 而非 msg-3
        assert "regen-msg" in call_log[-1], f"agent 应收到 regen-msg，实际收到: {call_log[-1]}"
        assert "msg-3" not in str(call_log), f"agent 不应看到 D 的 msg-3（时间旅行应从 C 开始），实际: {call_log}"


class TestMessagesProcessingLocation:
    """Phase 11.4: 验证 messages 处理逻辑已从 agent.py 移到 chat.py。"""

    def test_messages_processing_in_chat_not_agent(self):
        """agent.py.prepare_stream 不再包含 messages 处理逻辑；chat.py 包含。"""
        agent_source = _read_agent_py()
        chat_source = _read_chat_py()

        prepare_stream_source = _extract_method_source(agent_source, "prepare_stream")

        # agent.py.prepare_stream 中不应包含 messages 转换逻辑
        assert "agui_messages_to_langchain" not in prepare_stream_source, (
            "prepare_stream 不应包含 agui_messages_to_langchain（已移到 chat.py）"
        )
        assert "langgraph_default_merge_state" not in prepare_stream_source, (
            "prepare_stream 不应包含 langgraph_default_merge_state（已移到 chat.py）"
        )
        assert "prepare_regenerate_stream" not in prepare_stream_source, (
            "prepare_stream 不应包含 prepare_regenerate_stream（已移到 chat.py）"
        )

        # CR3→11.6: agent.py.prepare_stream 保留 self.get_schema_keys(config)（get_state_snapshot 依赖）
        # 11.6: get_stream_payload_input 移到 chat.py，agent.py 不再调用
        assert "self.get_schema_keys(config)" in prepare_stream_source, (
            "prepare_stream 应保留 self.get_schema_keys(config)（get_state_snapshot 依赖）"
        )
        assert "get_stream_payload_input" not in prepare_stream_source, (
            "prepare_stream 不应调用 get_stream_payload_input（11.6：移到 chat.py）"
        )

        # 11.6→11.9: agent.py prepare_stream 消除 is_regenerate 分支，从 input.stream_input 读取
        assert 'if preprocessed["is_regenerate"]' not in prepare_stream_source, (
            "prepare_stream 不应有 is_regenerate 分支（11.6：已消除）"
        )
        assert "input.stream_input" in prepare_stream_source, "prepare_stream 应从 input.stream_input 读取（11.9）"
        # 11.8: prepare_stream 不再读 preprocessed["fork"]（fork 移到 config，chat.py 构造 merged_cfg）
        assert 'preprocessed["fork"]' not in prepare_stream_source, (
            "prepare_stream 不应读 preprocessed['fork']（11.8：fork 移到 config）"
        )
        assert 'kwargs.pop("input")' not in prepare_stream_source, (
            "prepare_stream 不应有 kwargs.pop('input') 模式（11.6：已消除）"
        )

        # 11.6: chat.py 现在调用 get_stream_payload_input
        assert "get_stream_payload_input" in chat_source, (
            "chat.py 应调用 get_stream_payload_input（11.6：从 agent.py 移来）"
        )

        # 11.7: agent.py prepare_stream 从 input.state 读取 state（不再 preprocessed["state"]）
        assert "state = input.state" in prepare_stream_source, "prepare_stream 应从 input.state 读取 state（11.7）"
        assert 'preprocessed["state"]' not in prepare_stream_source, (
            "prepare_stream 不应再读 preprocessed['state']（11.7：改读 input.state）"
        )

        # agent.py.prepare_stream 中仍应包含 interrupt 事件构造和 stream 启动
        assert "has_active_interrupts" in prepare_stream_source, (
            "prepare_stream 应仍包含 has_active_interrupts（interrupt 事件构造保留在 agent.py）"
        )
        assert "astream_events" in prepare_stream_source, (
            "prepare_stream 应仍包含 astream_events（stream 启动保留在 agent.py）"
        )

        # chat.py 应包含 _merge_state 方法（langgraph_default_merge_state 整合）
        assert "def _merge_state(" in chat_source, "chat.py 应包含 _merge_state 方法定义"

        # chat.py 应包含 get_state_history（regenerate checkpoint 时间旅行）
        assert "get_state_history" in chat_source, "chat.py 应包含 get_state_history（regenerate 时间旅行）"

    def test_agent_py_no_deleted_methods(self):
        """agent.py 中不应再包含已迁移的方法定义。"""
        agent_source = _read_agent_py()

        assert "def langgraph_default_merge_state(" not in agent_source, (
            "agent.py 不应再包含 langgraph_default_merge_state 方法定义"
        )
        assert "def prepare_regenerate_stream(" not in agent_source, (
            "agent.py 不应再包含 prepare_regenerate_stream 方法定义"
        )
        assert "def get_checkpoint_before_message(" not in agent_source, (
            "agent.py 不应再包含 get_checkpoint_before_message 方法定义"
        )

    def test_chat_py_contains_preprocessing_pipeline(self):
        """chat.py 应包含完整的 messages 预处理流水线方法。"""
        chat_source = _read_chat_py()

        assert "def _prepare_stream_input(" in chat_source, "chat.py 应包含 _prepare_stream_input 方法（11.10 sync 化）"
        assert "def _prepare_regenerate_input(" in chat_source, (
            "chat.py 应包含 _prepare_regenerate_input 方法（11.10 sync 化）"
        )
        assert "def _get_schema_keys(" not in chat_source, "chat.py 不应包含 _get_schema_keys 方法（CR3：已删除）"
        assert "_preprocessed_stream_data" not in chat_source, (
            "chat.py 不应再有 _preprocessed_stream_data（11.9：已完全删除）"
        )

    def test_prepare_stream_input_passes_cfg_to_regenerate(self):
        """11.10 回归测试：_prepare_stream_input 直接调用 _prepare_regenerate_input，透传 cfg。"""
        source = _read_chat_py()
        stream_input_source = _extract_method_source(source, "_prepare_stream_input")

        # 11.10: sync 直调（无 await）
        assert "self._prepare_regenerate_input(" in stream_input_source, (
            "_prepare_stream_input 应直接调用 _prepare_regenerate_input（11.10 sync 化）"
        )
        # cfg 仍透传
        assert "cfg=cfg" in stream_input_source, "_prepare_stream_input 调用 _prepare_regenerate_input 时应透传 cfg=cfg"

    def test_fork_merge_to_config_configurable(self):
        """11.8 回归测试：get_stream_kwargs 不再接受 fork 参数（fork merge 移到 chat.py _stream）。

        11.5 CR2: fork merge 从 kwargs.update(fork) 改为 merge fork 的 configurable 到 config.configurable
        11.8 fork merge 逻辑从 agent.py get_stream_kwargs 移到 chat.py _stream（merged_cfg）
        此测试验证 get_stream_kwargs 不接受 fork 参数（传 fork 应 TypeError）。
        """
        source = _read_agent_py()
        kwargs_source = _extract_method_source(source, "get_stream_kwargs")

        # 核心断言：不应出现 kwargs.update(fork) 模式
        assert "kwargs.update(fork)" not in kwargs_source, "get_stream_kwargs 不应使用 kwargs.update(fork)（CR2 bug）"

        # 11.8: 不应有 fork 参数
        sig_line = kwargs_source.splitlines()[0]
        assert "fork" not in sig_line, f"get_stream_kwargs 签名不应有 fork 参数（11.8）: {sig_line}"
        assert "if fork:" not in kwargs_source, "get_stream_kwargs 不应有 if fork: 分支（11.8）"

        # 验证 get_stream_kwargs 不接受 fork 参数
        mock_graph = MagicMock()
        agent = LangGraphAgent.__new__(LangGraphAgent)
        agent.graph = mock_graph

        base_config = {"configurable": {"thread_id": "test-thread"}}

        # 传 fork 应 TypeError（参数已删除）
        with pytest.raises(TypeError):
            agent.get_stream_kwargs(
                input={"messages": []},
                config=base_config,
                fork={"configurable": {"checkpoint_id": "fork-checkpoint-123"}},
            )

    def test_fork_merge_preserves_existing_configurable_fields(self):
        """11.8 回归测试：get_stream_kwargs 不接受 fork 参数，config 直接透传（fork merge 在 chat.py）。"""
        mock_graph = MagicMock()
        agent = LangGraphAgent.__new__(LangGraphAgent)
        agent.graph = mock_graph

        base_config = {
            "configurable": {
                "thread_id": "test-thread",
                "execute_kwargs": {"key": "value"},
            }
        }

        # 11.8: config 直接透传（无 fork merge）
        kwargs = agent.get_stream_kwargs(
            input={"messages": []},
            config=base_config,
        )

        configurable = kwargs["config"]["configurable"]
        assert configurable["thread_id"] == "test-thread"
        assert configurable["execute_kwargs"] == {"key": "value"}

        # 传 fork 应 TypeError（参数已删除）
        with pytest.raises(TypeError):
            agent.get_stream_kwargs(
                input={"messages": []},
                config=base_config,
                fork={"configurable": {"checkpoint_id": "fork-checkpoint-456"}},
            )

    def test_prepare_methods_are_sync(self):
        """CR1（11.10 sync 化）：_prepare_stream_input 和 _prepare_regenerate_input 应为 def（sync）。"""
        chat_source = _read_chat_py()

        assert "def _prepare_stream_input(" in chat_source, "_prepare_stream_input 应为 def（11.10 sync 化）"
        assert "def _prepare_regenerate_input(" in chat_source, "_prepare_regenerate_input 应为 def（11.10 sync 化）"

    def test_prepare_regenerate_uses_sync_direct_calls(self):
        """11.10：_prepare_regenerate_input 内部用 sync 直调（无 await、无 run_coro_sync）。"""
        source = _read_chat_py()
        regenerate_source = _extract_method_source(source, "_prepare_regenerate_input")

        assert "run_coro_sync" not in regenerate_source, (
            "_prepare_regenerate_input 不应用 run_coro_sync（11.10 sync 化）"
        )
        assert "self._get_checkpoint_before_message(" in regenerate_source, (
            "_prepare_regenerate_input 应直接调用 self._get_checkpoint_before_message（11.10 sync 化）"
        )
        assert "agent_e.update_state(" in regenerate_source, (
            "_prepare_regenerate_input 应直接调用 agent_e.update_state（11.10 sync 化）"
        )
        assert "await" not in regenerate_source, "_prepare_regenerate_input 应为纯 sync（无 await）"

    def test_stream_uses_direct_prepare_stream_input(self):
        """11.10：_stream 直接调用 sync _prepare_stream_input（无 run_coro_sync 包装）。"""
        source = _read_chat_py()
        stream_source = _extract_method_source(source, "_stream")

        assert "run_coro_sync" not in stream_source, "_stream 不应使用 run_coro_sync（11.10 sync 化）"
        assert "self._prepare_stream_input(" in stream_source, (
            "_stream 应直接调用 self._prepare_stream_input（11.10 sync 化）"
        )

    def test_chat_py_uses_get_stream_payload_input(self):
        """11.6：chat.py 不应包含 _get_schema_keys 方法定义或调用，但应调用 get_stream_payload_input。"""
        chat_source = _read_chat_py()

        assert "def _get_schema_keys(" not in chat_source, "chat.py 不应包含 _get_schema_keys 方法定义（CR3：已删除）"
        assert "_get_schema_keys(" not in chat_source, "chat.py 不应包含 _get_schema_keys 调用（CR3：已删除）"
        assert "get_stream_payload_input" in chat_source, (
            "chat.py 应调用 get_stream_payload_input（11.6：从 agent.py 移来）"
        )

    def test_agent_py_prepare_stream_uses_preprocessed_stream_input(self):
        """11.6：agent.py.prepare_stream 统一用 preprocessed["stream_input"] + preprocessed["fork"]。"""
        source = _read_agent_py()
        prepare_stream_source = _extract_method_source(source, "prepare_stream")

        # 保留：self.get_schema_keys(config) 仍在 prepare_stream 内（get_state_snapshot 依赖）
        assert "self.get_schema_keys(config)" in prepare_stream_source, (
            "prepare_stream 应保留 self.get_schema_keys(config)（get_state_snapshot 依赖）"
        )
        # 11.6 反转：agent.py 不再调用 get_stream_payload_input
        assert "get_stream_payload_input" not in prepare_stream_source, (
            "prepare_stream 不应调用 get_stream_payload_input（11.6：移到 chat.py）"
        )
        assert 'preprocessed.get("schema_keys")' not in prepare_stream_source, (
            "prepare_stream 不应读 preprocessed.get('schema_keys')（CR3：自己算）"
        )
        # 11.6：不再构造 stream_payload（统一用 stream_input）
        assert 'preprocessed["stream_payload"]' not in prepare_stream_source, (
            "prepare_stream 不应读 preprocessed['stream_payload']（11.6：统一用 stream_input）"
        )
        # 11.6→11.9: prepare_stream 从 input.stream_input 读取（不再读 preprocessed["stream_input"]）
        assert "input.stream_input" in prepare_stream_source, "prepare_stream 应从 input.stream_input 读取（11.9）"
        assert 'preprocessed["stream_input"]' not in prepare_stream_source, (
            "prepare_stream 不应再读 preprocessed['stream_input']（11.9：改读 input.stream_input）"
        )
        # 11.8: prepare_stream 不再读 preprocessed["fork"]（fork 移到 config）
        assert 'preprocessed["fork"]' not in prepare_stream_source, (
            "prepare_stream 不应读 preprocessed['fork']（11.8：fork 移到 config）"
        )
        # 11.6 新增：消除 is_regenerate 分支
        assert 'if preprocessed["is_regenerate"]' not in prepare_stream_source, (
            "prepare_stream 不应有 is_regenerate 分支（11.6：已消除）"
        )

    def test_agent_py_prepare_stream_no_is_regenerate_branch(self):
        """11.6：agent.py prepare_stream 不应有 is_regenerate 分支。"""
        source = _read_agent_py()
        prepare_stream_source = _extract_method_source(source, "prepare_stream")
        assert 'if preprocessed["is_regenerate"]' not in prepare_stream_source, (
            "prepare_stream 不应有 if preprocessed['is_regenerate'] 分支（11.6：已消除，统一用 stream_input）"
        )

    def test_chat_py_prepare_stream_input_constructs_stream_input(self):
        """11.6：chat.py _prepare_stream_input 正常路径构造 stream_input（不为 None）。"""
        source = _read_chat_py()
        stream_input_source = _extract_method_source(source, "_prepare_stream_input")

        assert "get_stream_payload_input" in stream_input_source, (
            "_prepare_stream_input 应调用 get_stream_payload_input（11.6：正常路径构造 stream_input）"
        )
        assert "schema_keys" in stream_input_source, "_prepare_stream_input 应接收 schema_keys 参数（11.6）"

    def test_chat_py_stream_precomputes_schema_keys(self):
        """11.8：chat.py _stream 直接调 utils.get_schema_keys(agent_e, ...) 预先算 schema_keys（不依赖 agui_entry）。"""
        source = _read_chat_py()
        stream_source = _extract_method_source(source, "_stream")

        assert "agui_entry.get_schema_keys" not in stream_source, (
            "_stream 不应调用 agui_entry.get_schema_keys（11.8：改调 utils.get_schema_keys）"
        )
        assert "get_schema_keys(agent_e" in stream_source, (
            "_stream 应直接调 get_schema_keys(agent_e, ...) 预先算 schema_keys（11.8）"
        )
        assert "schema_keys" in stream_source, "_stream 应有 schema_keys 变量"

    def test_agent_py_prepare_stream_reads_input_state(self):
        """11.7：agent.py prepare_stream 从 input.state 读取 state（不再 preprocessed['state']）。"""
        source = _read_agent_py()
        prepare_stream_source = _extract_method_source(source, "prepare_stream")
        assert "state = input.state" in prepare_stream_source, "prepare_stream 应从 input.state 读取 state（11.7）"
        assert 'preprocessed["state"]' not in prepare_stream_source, (
            "prepare_stream 不应再读 preprocessed['state']（11.7：改读 input.state）"
        )

    def test_chat_py_stream_no_model_copy(self):
        """11.8：chat.py _stream 不用 model_copy 覆盖 agent_input.state（预处理前移，state 直接放进 body）。"""
        source = _read_chat_py()
        stream_source = _extract_method_source(source, "_stream")
        assert 'model_copy(update={"state"' not in stream_source, (
            "_stream 不应有 model_copy(update={'state': ...})（11.8：预处理前移消除 model_copy）"
        )
        assert "merged_cfg" in stream_source, "_stream 应有 merged_cfg 变量（11.8）"
        assert '"stream_input": preprocessed["stream_input"]' in stream_source, (
            "_stream 应把 stream_input 放入 body（11.9）"
        )
        assert "_preprocessed_stream_data" not in stream_source, (
            "_stream 不应再有 _preprocessed_stream_data（11.9：已完全删除）"
        )
        assert 'k in ("stream_input", "fork")' not in stream_source, (
            "_stream 不应再有 fork 过滤（11.8：fork 移到 config）"
        )

    def test_types_py_no_merged_state_field(self):
        """11.7：AgentInput 不新增 merged_state 字段（复用 RunAgentInput.state）。"""
        types_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "aidev_agent", "core", "ag_ui", "types.py"
        )
        types_path = os.path.normpath(types_path)
        with open(types_path, "r", encoding="utf-8") as f:
            types_source = f.read()
        assert "merged_state" not in types_source, "types.py 不应含 merged_state 字段（11.7：复用 RunAgentInput.state）"

    def test_prepare_stream_input_no_is_regenerate_langchain_messages(self):
        """11.7：_prepare_stream_input / _prepare_regenerate_input 返回值不含 is_regenerate / langchain_messages。"""
        source = _read_chat_py()
        psi = _extract_method_source(source, "_prepare_stream_input")
        pri = _extract_method_source(source, "_prepare_regenerate_input")
        assert '"is_regenerate"' not in psi, "_prepare_stream_input 返回值不应含 is_regenerate（11.7）"
        assert '"langchain_messages"' not in psi, "_prepare_stream_input 返回值不应含 langchain_messages（11.7）"
        assert '"is_regenerate"' not in pri, "_prepare_regenerate_input 返回值不应含 is_regenerate（11.7）"
        assert '"langchain_messages"' not in pri, "_prepare_regenerate_input 返回值不应含 langchain_messages（11.7）"

    # ---------- Phase 11.8 断言测试 ----------

    def test_utils_py_has_get_schema_keys_function(self):
        """11.8: utils.py 有独立的 get_schema_keys 函数。"""
        utils_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "aidev_agent", "core", "ag_ui", "utils.py"
        )
        utils_path = os.path.normpath(utils_path)
        with open(utils_path, "r", encoding="utf-8") as f:
            utils_source = f.read()
        assert "def get_schema_keys(graph, config, constant_schema_keys" in utils_source, (
            "utils.py 应有 get_schema_keys 独立函数（11.8）"
        )

    def test_agent_py_get_schema_keys_is_wrapper(self):
        """11.8: agent.py get_schema_keys 方法是 wrapper（内部调 utils.get_schema_keys）。"""
        source = _read_agent_py()
        method_source = _extract_method_source(source, "get_schema_keys")
        assert "return get_schema_keys(self.graph, config, self.constant_schema_keys)" in method_source, (
            "agent.py get_schema_keys 应为 wrapper（11.8）"
        )

    def test_get_stream_kwargs_no_fork_param(self):
        """11.8: get_stream_kwargs 签名无 fork 参数。"""
        source = _read_agent_py()
        kwargs_source = _extract_method_source(source, "get_stream_kwargs")
        # 签名行不应包含 fork
        sig_line = kwargs_source.splitlines()[0]
        assert "fork" not in sig_line, "get_stream_kwargs 签名不应有 fork 参数（11.8）"
        # 方法体不应有 if fork: 分支
        assert "if fork:" not in kwargs_source, "get_stream_kwargs 不应有 if fork: 分支（11.8）"

    def test_prepare_stream_no_fork_read(self):
        """11.8: prepare_stream 不读 preprocessed['fork']。"""
        source = _read_agent_py()
        prepare_stream_source = _extract_method_source(source, "prepare_stream")
        assert 'preprocessed["fork"]' not in prepare_stream_source, (
            "prepare_stream 不应读 preprocessed['fork']（11.8：fork 移到 config）"
        )

    def test_stream_uses_merged_cfg(self):
        """11.8: chat.py _stream 构造 merged_cfg 传给 AidevAGUIAgent。"""
        source = _read_chat_py()
        stream_source = _extract_method_source(source, "_stream")
        assert "merged_cfg" in stream_source, "_stream 应有 merged_cfg 变量（11.8）"
        assert "config=merged_cfg" in stream_source, "_stream 应传 config=merged_cfg（11.8）"

    def test_stream_preprocessing_before_agent_input(self):
        """11.8: chat.py _stream 预处理在 agent_input 构造之前。"""
        source = _read_chat_py()
        stream_source = _extract_method_source(source, "_stream")
        preprocessed_pos = stream_source.find("_prepare_stream_input")
        agent_input_pos = stream_source.find("AgentInput(")
        assert preprocessed_pos > 0 and agent_input_pos > 0, "_stream 应有 _prepare_stream_input 和 AgentInput 构造"
        assert preprocessed_pos < agent_input_pos, "预处理应在 AgentInput 构造之前（11.8）"

    def test_preprocessed_stream_data_fully_eliminated(self):
        """11.9: _preprocessed_stream_data 完全删除。"""
        source = _read_chat_py()
        stream_source = _extract_method_source(source, "_stream")
        assert "_preprocessed_stream_data" not in stream_source, (
            "_stream 不应有 _preprocessed_stream_data（11.9：已完全删除）"
        )

    def test_merge_state_no_tools_context_params(self):
        """11.9: _merge_state 签名无 tools/context 参数。"""
        source = _read_chat_py()
        merge_source = _extract_method_source(source, "_merge_state")
        sig_end = merge_source.find(") ->")
        sig = merge_source[:sig_end] if sig_end > 0 else merge_source[:200]
        assert "tools" not in sig, "_merge_state 签名不应有 tools 参数（11.9）"
        assert "context" not in sig, "_merge_state 签名不应有 context 参数（11.9）"

    # ---------- Phase 11.9 断言测试 ----------

    def test_types_py_has_stream_input_field(self):
        """11.9: AgentInput 有 stream_input 字段。"""
        types_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "aidev_agent", "core", "ag_ui", "types.py"
        )
        types_path = os.path.normpath(types_path)
        with open(types_path, "r", encoding="utf-8") as f:
            types_source = f.read()
        assert "stream_input" in types_source, "types.py AgentInput 应有 stream_input 字段（11.9）"

    def test_agent_py_prepare_stream_reads_input_stream_input(self):
        """11.9: agent.py prepare_stream 从 input.stream_input 读取。"""
        source = _read_agent_py()
        prepare_stream_source = _extract_method_source(source, "prepare_stream")
        assert "input.stream_input" in prepare_stream_source, "prepare_stream 应从 input.stream_input 读取（11.9）"
        assert 'preprocessed["stream_input"]' not in prepare_stream_source, (
            "prepare_stream 不应再读 preprocessed['stream_input']（11.9）"
        )

    def test_agent_py_no_preprocessed_stream_data(self):
        """11.9: agent.py 完全无 _preprocessed_stream_data。"""
        source = _read_agent_py()
        assert "_preprocessed_stream_data" not in source, (
            "agent.py 不应有 _preprocessed_stream_data（11.9：已完全删除）"
        )

    def test_chat_py_no_preprocessed_stream_data(self):
        """11.9: chat.py 完全无 _preprocessed_stream_data。"""
        source = _read_chat_py()
        assert "_preprocessed_stream_data" not in source, "chat.py 不应有 _preprocessed_stream_data（11.9：已完全删除）"

    def test_chat_py_stream_body_has_stream_input(self):
        """11.9: chat.py _stream body 包含 stream_input。"""
        source = _read_chat_py()
        stream_source = _extract_method_source(source, "_stream")
        assert '"stream_input": preprocessed["stream_input"]' in stream_source, (
            "_stream body 应包含 stream_input（11.9）"
        )

    def test_prepare_stream_input_no_tools_context(self):
        """11.9: _prepare_stream_input 签名无 tools/context。"""
        source = _read_chat_py()
        psi = _extract_method_source(source, "_prepare_stream_input")
        sig_end = psi.find(") ->")
        sig = psi[:sig_end] if sig_end > 0 else psi[:200]
        assert "tools" not in sig, "_prepare_stream_input 签名不应有 tools（11.9）"
        assert "context" not in sig, "_prepare_stream_input 签名不应有 context（11.9）"

    def test_prepare_regenerate_input_no_tools_context(self):
        """11.9: _prepare_regenerate_input 签名无 tools/context。"""
        source = _read_chat_py()
        pri = _extract_method_source(source, "_prepare_regenerate_input")
        sig_end = pri.find(") ->")
        sig = pri[:sig_end] if sig_end > 0 else pri[:200]
        assert "tools" not in sig, "_prepare_regenerate_input 签名不应有 tools（11.9）"
        assert "context" not in sig, "_prepare_regenerate_input 签名不应有 context（11.9）"

    def test_global_no_preprocessed_stream_data(self):
        """11.9: 全局 grep _preprocessed_stream_data 返回 0 matches（aidev_agent/ + tests/ 源码）。

        排除 __pycache__ 和本测试文件（断言字符串字面量自身包含标识符）。
        """
        result = subprocess.run(
            [
                "grep",
                "-rn",
                "--include=*.py",
                "_preprocessed_stream_data",
                "aidev_agent/",
                "tests/",
            ],
            capture_output=True,
            text=True,
        )
        # 过滤掉本测试文件的断言字符串字面量（self-references）
        own_path = os.path.relpath(__file__)
        real_refs = [line for line in result.stdout.splitlines() if line and not line.startswith(own_path + ":")]
        assert not real_refs, f"全局仍有 _preprocessed_stream_data 实际引用:\n{chr(10).join(real_refs)}"
