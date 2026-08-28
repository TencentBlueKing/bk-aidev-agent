# -*- coding: utf-8 -*-
"""企微渠道 Agent 策略单元测试。

聚焦主流程链路覆盖：
  企微回调 → resolve_strategy → Strategy.execute → consume_flow_stream
  → handle_flow_custom_event → LlmChunkMsg → RabbitMQ

测试分层：
1. resolve_strategy — 入口分发：chat / flow / 异常降级
2. FlowAgentStrategy.execute — 端到端：RTX解析 → session → agent执行 → RabbitMQ
3. ChatAgentStrategy.execute — Chat 路径验证
4. consume_flow_stream — 完整生命周期 / RUN_ERROR 终止 / 异常降级
5. handle_flow_custom_event — start/result/end 三阶段展示策略验证
6. resolve_channel_admin_rtx — 认证链路：正常获取 / 降级兜底
7. WxFlowAgentClient — 认证注入验证
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from aidev_wxbot.wxaibot.auth import WxFlowAgentClient, resolve_channel_admin_rtx
from aidev_wxbot.wxaibot.context import LlmChunkMsg
from aidev_wxbot.wxaibot.formatters import handle_flow_custom_event
from aidev_wxbot.wxaibot.strategies import (
    WECOM_AGENT_EXECUTION_POLICY,
    WECOM_AGENT_TEMPERATURE,
    WECOM_LONG_CONNECTION_EXECUTION_POLICY,
    ChatAgentStrategy,
    FlowAgentStrategy,
    resolve_strategy,
)
from aidev_wxbot.wxaibot.stream import consume_flow_stream

# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_rabbitmq():
    """Mock RabbitMQ 客户端"""
    client = MagicMock()
    client.declare_queue = MagicMock(return_value=True)
    client.publish_message = MagicMock(return_value=True)
    return client


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n"


# ---------------------------------------------------------------------------
# 1. resolve_strategy — 入口分发
# ---------------------------------------------------------------------------


class TestResolveStrategy:
    @pytest.mark.parametrize("agent_type, expected", [("chat", ChatAgentStrategy), ("flow", FlowAgentStrategy)])
    @patch("aidev_wxbot.wxaibot.strategies.AgentConfigFetcher.get_info")
    def test_dispatches_correct_strategy(self, mock_config, agent_type, expected):
        """正常分发：chat → ChatAgentStrategy，flow → FlowAgentStrategy"""
        mock_config.return_value = {"agent_type": agent_type}
        assert isinstance(resolve_strategy("user"), expected)

    @pytest.mark.parametrize("config", [{}, {"agent_type": ""}, {"agent_type": "unknown"}])
    @patch("aidev_wxbot.wxaibot.strategies.AgentConfigFetcher.get_info")
    def test_fallback_to_chat(self, mock_config, config):
        """缺失/空/未知 agent_type 均降级为 Chat"""
        mock_config.return_value = config
        assert isinstance(resolve_strategy("user"), ChatAgentStrategy)

    @patch("aidev_wxbot.wxaibot.strategies.AgentConfigFetcher.get_info", side_effect=Exception("API down"))
    def test_api_exception_fallback(self, _):
        """API 异常降级为 Chat"""
        assert isinstance(resolve_strategy("user"), ChatAgentStrategy)


# ---------------------------------------------------------------------------
# 2. FlowAgentStrategy.execute — 端到端集成
# ---------------------------------------------------------------------------


class TestFlowAgentStrategyExecute:
    @patch("aidev_wxbot.wxaibot.formatters.AgentHelper.build_session_detail_url", return_value="")
    @patch("aidev_wxbot.wxaibot.strategies.AgentHelper.get_client")
    @patch("aidev_wxbot.wxaibot.strategies.WxFlowAgentClient")
    @patch("aidev_wxbot.wxaibot.strategies.SessionManager")
    @patch("aidev_wxbot.wxaibot.strategies.AgentInstanceFactory")
    @patch("aidev_wxbot.wxaibot.strategies.AGUISessionWriter")
    def test_full_execute_pipeline(
        self,
        mock_writer,
        mock_factory,
        mock_session_cls,
        mock_flow_client,
        mock_get_client,
        mock_build_detail_url,
        mock_rabbitmq,
    ):
        """主流程：RTX解析 → session创建 → 用户输入保存 → agent构建执行 → SSE消费写入RabbitMQ"""
        session_manager = mock_session_cls.return_value
        session_manager.get_or_create_by_thread_id.return_value = "sc_abc"

        # 模拟 agent 返回完整 SSE 流
        mock_inst = MagicMock()
        mock_inst.execute.return_value = iter(
            [
                _sse({"type": "RUN_STARTED", "run_id": "r1", "thread_id": "t1"}),
                _sse({"type": "CUSTOM", "name": "flow_agent_start", "value": [{"task_id": "999"}]}),
                _sse(
                    {
                        "type": "CUSTOM",
                        "name": "flow_agent_result",
                        "value": [
                            {
                                "task_state": "RUNNING",
                                "nodes": {"n1": {"name": "步骤1", "state": "RUNNING", "elapsed_time": 5}},
                                "statistics": {"total": 1, "state_counts": {"RUNNING": 1}},
                            }
                        ],
                    }
                ),
                _sse(
                    {
                        "type": "CUSTOM",
                        "name": "flow_agent_end",
                        "value": [
                            {
                                "task_id": "999",
                                "task_outputs": [{"key": "out", "value": "done"}],
                            }
                        ],
                    }
                ),
                _sse({"type": "RUN_FINISHED", "run_id": "r1", "thread_id": "t1"}),
            ]
        )
        mock_factory.build_agent.return_value = mock_inst

        FlowAgentStrategy().execute(
            content="运行流程",
            stream_id="s_1_1000",
            username="wxid_123",
            thread_id="t1",
            group_id="g1",
            rabbitmq_client=mock_rabbitmq,
        )

        # 验证完整调用链
        mock_session_cls.assert_called_once_with(username="wxid_123")
        session_manager.get_or_create_by_thread_id.assert_called_once_with("t1", channel_type="rtx")
        session_manager.save_content.assert_called_once()
        save_kwargs = session_manager.save_content.call_args.kwargs
        assert save_kwargs["session_code"] == "sc_abc"
        assert save_kwargs["role"] == "user"
        assert save_kwargs["content"] == "运行流程"
        mock_factory.build_agent.assert_called_once()  # agent 通过工厂构建

        # 验证传给工厂的关键参数（agent_type=FLOW、session_code、flow_start_params 透传）
        factory_kwargs = mock_factory.build_agent.call_args[1]
        assert factory_kwargs["session_code"] == "sc_abc"
        assert factory_kwargs["flow_start_params"]["session_code"] == "sc_abc"
        assert factory_kwargs["flow_resource_manager"] is mock_flow_client.return_value
        mock_get_client.assert_called_once_with()
        mock_build_detail_url.assert_called_once_with("sc_abc")

        # start 仅缓存 task_id；result 和 end 各写入一次。
        assert mock_rabbitmq.publish_message.call_count == 2


# ---------------------------------------------------------------------------
# 3. ChatAgentStrategy.execute
# ---------------------------------------------------------------------------


class TestChatAgentStrategyExecute:
    @patch("aidev_wxbot.wxaibot.strategies.AgentExecutor.run_chat_completion_with_thread_id")
    @patch("aidev_wxbot.wxaibot.strategies.build_execute_kwargs")
    def test_long_connection_uses_sdk_retry_and_strict_file_delivery_policy(self, mock_build, mock_run):
        mock_build.return_value = MagicMock(stream=True)
        mock_run.return_value = (iter(()), "session-1")

        ChatAgentStrategy().open_stream(
            content="query",
            username="user",
            thread_id="thread",
            group_id="group",
            retry_strategy="sdk",
        )

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["retry_strategy"] == "sdk"
        assert call_kwargs["transient_system_prompt"] == WECOM_LONG_CONNECTION_EXECUTION_POLICY

    @patch("aidev_wxbot.wxaibot.strategies.AgentExecutor.run_chat_completion_with_thread_id")
    @patch("aidev_wxbot.wxaibot.strategies.build_execute_kwargs")
    def test_stream_mode_writes_to_rabbitmq(self, mock_build, mock_run, mock_rabbitmq):
        """Chat 流式模式：调用 chat completion → 内容写入 RabbitMQ"""
        mock_build.return_value = MagicMock(stream=True)
        mock_run.return_value = (
            iter(
                [
                    _sse({"type": "TEXT_MESSAGE_CONTENT", "delta": "你好"}),
                    _sse({"type": "RUN_FINISHED", "run_id": "r1", "thread_id": "t1"}),
                ]
            ),
            "sc_1",
        )

        ChatAgentStrategy().execute(
            content="hello",
            stream_id="s_1_1000",
            username="u",
            thread_id="t1",
            group_id="g1",
            rabbitmq_client=mock_rabbitmq,
        )

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["transient_system_prompt"] == WECOM_AGENT_EXECUTION_POLICY
        assert call_kwargs["enable_query_clarification"] is False
        assert call_kwargs["temperature"] == WECOM_AGENT_TEMPERATURE
        assert call_kwargs["retry_strategy"] is None
        assert mock_rabbitmq.publish_message.call_count >= 1


# ---------------------------------------------------------------------------
# 4. consume_flow_stream — SSE 消费核心逻辑
# ---------------------------------------------------------------------------


class TestConsumeFlowStream:
    def test_full_lifecycle_start_result_end(self, mock_rabbitmq):
        """完整生命周期：start → result×2 → end → FINISHED

        验证：think_content 累积执行过程，content 包含最终结果，is_finish=True
        """
        events = [
            {"type": "RUN_STARTED", "run_id": "r1", "thread_id": "t1"},
            {"type": "CUSTOM", "name": "flow_agent_start", "value": [{"task_id": "123"}]},
            {
                "type": "CUSTOM",
                "name": "flow_agent_result",
                "value": [
                    {
                        "task_state": "RUNNING",
                        "nodes": {"n1": {"name": "A", "state": "FINISHED", "elapsed_time": 10}},
                        "statistics": {"total": 1, "state_counts": {"FINISHED": 1}},
                    }
                ],
            },
            {
                "type": "CUSTOM",
                "name": "flow_agent_result",
                "value": [
                    {
                        "task_state": "RUNNING",
                        "nodes": {},
                        "statistics": {},
                    }
                ],
            },
            {
                "type": "CUSTOM",
                "name": "flow_agent_end",
                "value": [
                    {
                        "task_id": "123",
                        "task_outputs": [{"key": "out", "value": "ok"}],
                    }
                ],
            },
            {"type": "RUN_FINISHED", "run_id": "r1", "thread_id": "t1"},
        ]

        consume_flow_stream(iter([_sse(e) for e in events]), "s_1_1000", 1000.0, mock_rabbitmq)

        # start 仅缓存 task_id；result×2 和 end 共写入三次。
        assert mock_rabbitmq.publish_message.call_count == 3

        # 检查最后一次写入的消息是 is_finish=True 且 content 包含结果
        last_call_data = mock_rabbitmq.publish_message.call_args_list[-1][0][2]
        last_msg = last_call_data if isinstance(last_call_data, dict) else json.loads(last_call_data)
        assert last_msg["is_finish"] is True
        assert "完成" in last_msg["content"]

    def test_run_error_terminates_and_writes_error(self, mock_rabbitmq):
        """RUN_ERROR → 写入错误消息 + is_finish=True，后续事件不再处理"""
        events = [
            {"type": "RUN_STARTED", "run_id": "r1", "thread_id": "t1"},
            {"type": "RUN_ERROR", "message": "Gateway timeout"},
            {"type": "RUN_FINISHED", "run_id": "r1", "thread_id": "t1"},
        ]

        consume_flow_stream(iter([_sse(e) for e in events]), "s_1_1000", 1000.0, mock_rabbitmq)

        # RUN_ERROR 后应只有 1 次写入（错误消息），RUN_FINISHED 不应再触发写入
        assert mock_rabbitmq.publish_message.call_count == 1
        last_msg = mock_rabbitmq.publish_message.call_args_list[-1][0][2]
        if isinstance(last_msg, str):
            last_msg = json.loads(last_msg)
        assert last_msg["is_finish"] is True
        assert "出错" in last_msg["content"] or "timeout" in last_msg["content"]

    def test_malformed_json_graceful_degradation(self, mock_rabbitmq):
        """非法 JSON 行不崩溃，后续正常事件继续处理"""

        def gen():
            yield "data: {broken\n"
            yield _sse({"type": "CUSTOM", "name": "flow_agent_start", "value": [{"task_id": "1"}]})
            yield _sse({"type": "CUSTOM", "name": "flow_agent_end", "value": [{"task_id": "1", "task_outputs": {}}]})
            yield _sse({"type": "RUN_FINISHED", "run_id": "r1", "thread_id": "t1"})

        consume_flow_stream(gen(), "s_1_1000", 1000.0, mock_rabbitmq)

        # 非法行被跳过；start 仅缓存 task_id，end 写入一次。
        assert mock_rabbitmq.publish_message.call_count == 1


# ---------------------------------------------------------------------------
# 5. handle_flow_custom_event — 展示策略核心
# ---------------------------------------------------------------------------


class TestHandleFlowCustomEvent:
    """验证三阶段展示策略：start→缓存task_id, result→think(节点名称列表)+缓存nodes, end→content(最终状态)"""

    def test_start_saves_task_id(self, mock_rabbitmq):
        """flow_agent_start: 缓存 task_id，不写 think_content，content 为空"""
        chunk = LlmChunkMsg(stream_id="s_1_1000")
        handle_flow_custom_event("flow_agent_start", {"value": [{"task_id": "42"}]}, chunk, mock_rabbitmq)

        assert chunk._flow_task_id == "42"
        assert chunk._flow_nodes_initialized is False
        assert chunk.think_content == ""
        assert chunk.content == ""
        assert not chunk.is_finish

    def test_result_shows_node_names_and_caches_data(self, mock_rabbitmq):
        """flow_agent_result: 首次展示节点名称列表（无状态），缓存 nodes 和 task_state"""
        chunk = LlmChunkMsg(stream_id="s_1_1000")
        handle_flow_custom_event(
            "flow_agent_result",
            {
                "value": [
                    {
                        "task_state": "RUNNING",
                        "nodes": {
                            "n1": {"name": "数据清洗", "state": "FINISHED", "elapsed_time": 90},
                            "n2": {"name": "模型训练", "state": "RUNNING", "elapsed_time": 30},
                            "n3": {"name": "汇总", "state": "PENDING", "elapsed_time": 0},
                        },
                        "statistics": {"total": 3, "state_counts": {"FINISHED": 1, "RUNNING": 1, "PENDING": 1}},
                    }
                ]
            },
            chunk,
            mock_rabbitmq,
        )

        # 验证节点名称列表（无图标/状态/耗时）
        # 提取节点名称列表（按行分割，提取 "- 名称" 格式）
        think_lines = chunk.think_content.split("\n")
        node_names = [line.strip()[2:] for line in think_lines if line.strip().startswith("- ")]
        assert "数据清洗" in node_names
        assert "模型训练" in node_names
        assert "汇总" in node_names
        assert "共包含3个节点" in chunk.think_content
        # 验证缓存了 nodes 和 task_state
        assert chunk._flow_nodes_cache == {
            "n1": {"name": "数据清洗", "state": "FINISHED", "elapsed_time": 90},
            "n2": {"name": "模型训练", "state": "RUNNING", "elapsed_time": 30},
            "n3": {"name": "汇总", "state": "PENDING", "elapsed_time": 0},
        }
        assert chunk._flow_last_task_state == "RUNNING"
        # content 仍为空（中间状态）
        assert chunk.content == ""

    def test_end_success_uses_cached_state(self, mock_rabbitmq):
        """flow_agent_end 成功: 使用缓存的 nodes 展示最终状态，content 含结果"""
        chunk = LlmChunkMsg(stream_id="s_1_1000")
        # 模拟轮询过程已缓存了 nodes 和 task_state
        chunk._flow_task_id = "1"
        chunk._flow_nodes_cache = {
            "n1": {"name": "数据清洗", "state": "FINISHED", "elapsed_time": 90},
        }
        chunk._flow_last_task_state = "FINISHED"
        # flow_agent_end 事件不携带 nodes 和 state（仅失败时有 state）
        handle_flow_custom_event(
            "flow_agent_end",
            {
                "value": [
                    {
                        "task_id": "1",
                        "task_outputs": [{"key": "result", "value": "done"}],
                    }
                ]
            },
            chunk,
            mock_rabbitmq,
        )

        assert "完成" in chunk.content
        assert "result: done" in chunk.content
        # think_content 使用缓存的 nodes 展示最终状态（有图标）
        assert "成功" in chunk.think_content
        assert "数据清洗" in chunk.think_content
        assert chunk.is_finish

    def test_end_error_to_content(self, mock_rabbitmq):
        """flow_agent_end 失败: content 含中文失败状态，state 从 event 获取"""
        chunk = LlmChunkMsg(stream_id="s_1_1000")
        chunk._flow_task_id = "2"
        # 失败时 flow_agent_end 会携带 error=True 和 state
        handle_flow_custom_event(
            "flow_agent_end",
            {
                "value": [
                    {
                        "task_id": "2",
                        "error": True,
                        "state": "FAILED",
                    }
                ]
            },
            chunk,
            mock_rabbitmq,
        )

        assert "失败" in chunk.content
        assert "2" in chunk.content
        assert chunk.is_finish

    def test_value_none_no_crash(self, mock_rabbitmq):
        """value 为 None 时不崩溃（防御性边界）"""
        chunk = LlmChunkMsg(stream_id="s_1_1000")
        handle_flow_custom_event("flow_agent_start", {"value": None}, chunk, mock_rabbitmq)
        assert chunk._flow_task_id == "未知"


# ---------------------------------------------------------------------------
# 6. resolve_channel_admin_rtx — 认证链路
# ---------------------------------------------------------------------------


class TestResolveChannelAdminRtx:
    @patch("aidev_wxbot.wxaibot.auth.BkAiDevApi")
    def test_returns_contact_from_config(self, mock_api_cls):
        """正常路径：从渠道配置获取管理员 RTX"""
        mock_api_cls.return_value.retrieve_agent_channel_configs.return_value = [
            {"config": {"contact": "channel_admin_rtx"}}
        ]
        assert resolve_channel_admin_rtx("A000000A") == "channel_admin_rtx"

    @pytest.mark.parametrize(
        "configs",
        [
            [],  # 空列表
            [{"config": {}}],  # 无 contact 字段
            [{"config": None}],  # config 为 None
        ],
        ids=["empty", "no_contact", "config_none"],
    )
    @patch("aidev_wxbot.wxaibot.auth.BkAiDevApi")
    def test_fallback_to_original_username(self, mock_api_cls, configs):
        """异常路径：配置不可用时降级为原始 username"""
        mock_api_cls.return_value.retrieve_agent_channel_configs.return_value = configs
        assert resolve_channel_admin_rtx("A000000A") == "A000000A"

    @patch("aidev_wxbot.wxaibot.auth.BkAiDevApi")
    def test_api_exception_fallback(self, mock_api_cls):
        """API 异常不崩溃，降级为原始 username"""
        mock_api_cls.return_value.retrieve_agent_channel_configs.side_effect = Exception("500")
        assert resolve_channel_admin_rtx("fallback") == "fallback"


# ---------------------------------------------------------------------------
# 7. WxFlowAgentClient — 认证注入
# ---------------------------------------------------------------------------


class TestWxFlowAgentClient:
    @patch("aidev_wxbot.wxaibot.auth.resolve_channel_admin_rtx", return_value="admin_rtx")
    @patch("aidev_agent.packages.resource_manager.agent.BKAidevApi.get_client")
    def test_injects_rtx_auth_and_calls_downstream(self, mock_get_client, mock_resolve):
        """使用解析后的 RTX 获取认证 → 注入 headers → 调用下游 flow_agent_start"""
        mock_client = MagicMock()
        mock_client.api.flow_agent_start.return_value = {"data": {"task_id": "123"}}
        mock_get_client.return_value = mock_client

        result = WxFlowAgentClient("openid_xxx").start_flow_agent(data={"session_code": "sc1"})

        assert result["task_id"] == "123"
        # 验证通过 AgentResourceManager.get_client 调用了 BKAidevApi.get_client
        mock_get_client.assert_called_once()
