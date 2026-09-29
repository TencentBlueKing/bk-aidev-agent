# -*- coding: utf-8 -*-
"""
测试 knowledge.py 功能
"""

from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.core.nodes.knowledge import (
    AgentKnowledgeNode,
    AidevKnowledgeNode,
    KnowledgeInputState,
    make_knowledge_node,
)
from aidev_agent.enums import Decision
from aidev_agent.pydantic_models import AgentOptions, KnowledgebaseSettings, KnowledgeSettings
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore
from typing_extensions import TypedDict

# ============================================================================
# 测试状态定义
# ============================================================================


class KnowledgeState(TypedDict, total=False):
    """Knowledge 测试状态"""

    query: str
    input: str
    messages: list
    decision: Decision | None
    knowledge_content: list | None
    reference_doc: list | None
    retrieved_docs: list | None


# ============================================================================
# pytest fixtures
# ============================================================================


@pytest.fixture()
def mock_llm():
    """创建 mock 的 LLM"""
    llm = MagicMock()
    llm.invoke = MagicMock(return_value=MagicMock(content="mocked response"))
    return llm


@pytest.fixture()
def mock_knowledge_settings():
    """创建 mock 的 KnowledgeSettings"""
    return KnowledgeSettings()


# ============================================================================
# 辅助函数
# ============================================================================


def run_knowledge_node_in_graph(knowledge_node, state: dict) -> dict:
    """在图中运行 knowledge_node 并返回结果"""
    graph = StateGraph(KnowledgeState)
    graph.add_node("knowledge", knowledge_node)
    graph.add_edge(START, "knowledge")
    graph.add_edge("knowledge", END)

    store = InMemoryStore()
    compiled = graph.compile(store=store)
    result = compiled.invoke(state)
    return result


def create_mock_retrieve_result(
    decision: Decision = Decision.GENERAL_QA,
    reference_doc: list | None = None,
    knowledge_resources_emb_recalled: list | None = None,
):
    """创建 mock 的检索结果"""
    return {
        "decision": decision,
        "knowledge_resources_highly_relevant": [],
        "knowledge_resources_moderately_relevant": [],
        "knowledge_resources_lowly_relevant": [],
        "knowledge_content": ["mocked content"],
        "reference_doc": reference_doc or [],
        "knowledge_resources_emb_recalled": knowledge_resources_emb_recalled or [],
    }


# ============================================================================
# 测试 AgentKnowledgeNode 在 Graph 中的执行
# ============================================================================


class TestAgentKnowledgeNodeInGraph:
    """测试 AgentKnowledgeNode 在 Graph 中的执行"""

    def test_returns_agent_knowledge_node(self, mock_llm, mock_knowledge_settings):
        """测试 make_knowledge_node 返回 AgentKnowledgeNode 实例"""
        node = make_knowledge_node(llm=mock_llm, knowledge_query_options=mock_knowledge_settings)

        assert isinstance(node, AgentKnowledgeNode)
        assert node.llm is mock_llm
        assert node.knowledge_query_options is mock_knowledge_settings
        # 测试返回的节点有 retriever 属性
        assert hasattr(node, "retriever")
        assert node.retriever is not None
        # 测试返回的节点有 kb_retriever 属性
        assert hasattr(node, "kb_retriever")
        assert node.kb_retriever is not None

    @patch("aidev_agent.core.nodes.knowledge.KnowledgeRag")
    @patch("aidev_agent.core.nodes.knowledge.dispatch_custom_event")
    def test_state_return_with_input(self, mock_dispatch, mock_rag_class, mock_llm, mock_knowledge_settings):
        """测试使用 query 字段时的 state 返回"""
        # 配置 mock
        mock_rag_instance = MagicMock()
        mock_rag_instance.retrieve.return_value = create_mock_retrieve_result(
            reference_doc=[
                {
                    "metadata": {
                        "preview_path": "/path/to/file",
                        "path": "http://example.com/file",
                        "display_name": "test_file.txt",
                    }
                }
            ]
        )
        mock_rag_class.return_value = mock_rag_instance

        node = AgentKnowledgeNode(llm=mock_llm, knowledge_query_options=mock_knowledge_settings, chat_history=[])

        # 验证 query 作为参数调用
        result = run_knowledge_node_in_graph(node, {"query": "test query"})
        mock_rag_instance.retrieve.assert_called_once()
        assert "messages" in result
        assert len(result["messages"]) > 0
        assert mock_dispatch.call_count == 3
        assert "reference_doc" in result
        assert "metadata" in result["reference_doc"][0]

        # 验证使用了 input 字段作为查询
        mock_dispatch.call_count = 0
        result = run_knowledge_node_in_graph(node, {"input": "test input"})
        call_args = mock_rag_instance.retrieve.call_args
        assert call_args[0][0] == "test input"
        assert "messages" in result
        assert len(result["messages"]) > 0
        assert mock_dispatch.call_count == 3
        assert "reference_doc" in result
        assert "metadata" in result["reference_doc"][0]

        # 验证使用了 messages 的最后一条消息作为查询
        mock_dispatch.call_count = 0
        result = run_knowledge_node_in_graph(node, {"messages": [HumanMessage(content="test message content")]})
        call_args = mock_rag_instance.retrieve.call_args
        assert call_args[0][0] == "test message content"
        assert "messages" in result
        assert len(result["messages"]) > 0
        assert mock_dispatch.call_count == 3
        assert "reference_doc" in result
        assert "metadata" in result["reference_doc"][0]


# ============================================================================
# 测试 AidevKnowledgeNode
# ============================================================================
class TestAidevKnowledgeNode:
    """测试 AidevKnowledgeNode"""

    def test_init_with_params(self, mock_llm, mock_knowledge_settings):
        """测试默认参数初始化"""
        node = AidevKnowledgeNode(llm=mock_llm, knowledge_query_options=mock_knowledge_settings)

        assert node.score_threshold is None
        assert node.topk == 20
        # 测试自定义参数初始化
        node = AidevKnowledgeNode(
            llm=mock_llm,
            knowledge_query_options=mock_knowledge_settings,
            score_threshold=0.5,
            topk=10,
        )
        assert node.score_threshold == 0.5
        assert node.topk == 10

    @staticmethod
    def _build_agent_options_from_mock_query_request() -> AgentOptions:
        """按 AIDev 产品页旧入口构造 AgentOptions，相关依赖字段用 mock 代替。"""
        knowledge_index_service = MagicMock()
        knowledge_index_service.get_knowledge_base_index_config.side_effect = lambda i: {"index": f"kb-{i}"}
        knowledge_item_service = MagicMock()
        knowledge_item_service.get_knowledge_index_configs.side_effect = lambda i: [{"index": f"ki-{i}"}]

        query_parameters = MagicMock()
        query_parameters.knowledge_resource_reject_threshold = (0.3, 0.7)
        query_parameters.topk = 5
        query_parameters.knowledge_template_id = 9
        query_parameters.rejection_message = "拒答文案"

        query_request = MagicMock()
        query_request.knowledge_base_ids = [1, 2]
        query_request.knowledge_item_ids = [3]
        query_request.with_scalar_data = False
        query_request.query_record.query_parameters = query_parameters

        return AgentOptions(
            knowledge_query_options=KnowledgebaseSettings(
                knowledge_bases=[
                    {"id": i, "index_config": knowledge_index_service.get_knowledge_base_index_config(i)}
                    for i in query_request.knowledge_base_ids
                ],
                knowledge_items=[
                    {"id": i, "index_config": knowledge_item_service.get_knowledge_index_configs(i)}
                    for i in query_request.knowledge_item_ids
                ],
                knowledge_resource_reject_threshold=(0, 0)
                if query_request.with_scalar_data
                else query_request.query_record.query_parameters.knowledge_resource_reject_threshold,
                topk=query_request.query_record.query_parameters.topk,
                knowledge_template_id=query_request.query_record.query_parameters.knowledge_template_id,
                force_process_by_agent=True,
                with_scalar_data=query_request.with_scalar_data,
                rejection_message=query_request.query_record.query_parameters.rejection_message,
            )
        )

    def test_init_migrates_from_legacy_agent_options(self, mock_llm):
        """knowledge_query_options 未传入时，应从产品页旧版 agent_options 迁移。"""
        agent_options = self._build_agent_options_from_mock_query_request()

        node = AidevKnowledgeNode(
            llm=mock_llm,
            agent_options=agent_options,
            score_threshold=agent_options.knowledge_query_options.knowledge_resource_reject_threshold[0],
            topk=agent_options.knowledge_query_options.model_extra["topk"],
        )

        assert node.score_threshold == 0.3
        assert node.topk == 5
        assert node.knowledge_query_options.knowledge_bases == [
            {"id": 1, "index_config": {"index": "kb-1"}},
            {"id": 2, "index_config": {"index": "kb-2"}},
        ]
        assert node.knowledge_query_options.knowledge_items == [{"id": 3, "index_config": [{"index": "ki-3"}]}]
        assert node.knowledge_query_options.knowledge_resource_reject_threshold == (0.3, 0.7)
        assert node.knowledge_query_options.knowledge_resource_rough_recall_topk == 5
        assert node.knowledge_query_options.knowledge_template_id == 9
        assert node.knowledge_query_options.rejection_message == "拒答文案"

    def test_init_raises_without_knowledge_query_options_or_agent_options(self, mock_llm):
        """knowledge_query_options 和 agent_options 均未传入时应抛出异常。"""
        with pytest.raises(ValueError, match="knowledge_query_options is required"):
            AidevKnowledgeNode(llm=mock_llm)

    @patch("aidev_agent.core.nodes.knowledge.KnowledgeRag")
    def test_call_returns_retrieved_docs(self, mock_rag_class, mock_llm, mock_knowledge_settings):
        """测试 __call__ 返回 retrieved_docs"""
        mock_rag_instance = MagicMock()
        mock_rag_instance.retrieve.return_value = create_mock_retrieve_result(
            knowledge_resources_emb_recalled=[
                {"metadata": {"fine_grained_score": 0.9, "content": "doc1"}},
                {"metadata": {"fine_grained_score": 0.7, "content": "doc2"}},
                {"metadata": {"fine_grained_score": 0.5, "content": "doc3"}},
            ]
        )
        mock_rag_class.return_value = mock_rag_instance

        node = AidevKnowledgeNode(
            llm=mock_llm,
            knowledge_query_options=mock_knowledge_settings,
            score_threshold=0.6,
            topk=10,
        )
        result = run_knowledge_node_in_graph(node, {"query": "test query"})

        # WEB API 已完成过滤和排序，SDK 节点应原样透传。
        assert "retrieved_docs" in result
        assert len(result["retrieved_docs"]) == 3
        assert result["retrieved_docs"][0]["metadata"]["fine_grained_score"] == 0.9
        assert result["retrieved_docs"][1]["metadata"]["fine_grained_score"] == 0.7

    @patch("aidev_agent.core.nodes.knowledge.KnowledgeRag")
    def test_call_forwards_chat_history_to_retriever(self, mock_rag_class, mock_llm, mock_knowledge_settings):
        """查询节点应把调用方提供的历史消息传给查询预处理链路。"""
        mock_rag_instance = MagicMock()
        mock_rag_instance.retrieve.return_value = create_mock_retrieve_result()
        mock_rag_class.return_value = mock_rag_instance
        chat_history = [
            HumanMessage(content="Redis 为什么会超时？"),
            AIMessage(content="先确认连接池和慢查询。"),
        ]
        node = AidevKnowledgeNode(
            llm=mock_llm,
            knowledge_query_options=mock_knowledge_settings,
            chat_history=chat_history,
        )

        run_knowledge_node_in_graph(node, {"query": "那网络抖动呢？"})

        call_args = mock_rag_instance.retrieve.call_args
        assert call_args.args[2] == chat_history

    @patch("aidev_agent.core.nodes.knowledge.KnowledgeRag")
    def test_call_does_not_apply_topk_again(self, mock_rag_class, mock_llm, mock_knowledge_settings):
        """SDK 不应对 WEB API 的最终候选再次应用 topk。"""
        mock_rag_instance = MagicMock()
        mock_rag_instance.retrieve.return_value = create_mock_retrieve_result(
            knowledge_resources_emb_recalled=[
                {"metadata": {"fine_grained_score": 0.9}},
                {"metadata": {"fine_grained_score": 0.8}},
                {"metadata": {"fine_grained_score": 0.7}},
                {"metadata": {"fine_grained_score": 0.6}},
            ]
        )
        mock_rag_class.return_value = mock_rag_instance

        node = AidevKnowledgeNode(
            llm=mock_llm,
            knowledge_query_options=mock_knowledge_settings,
            topk=2,
        )

        state: KnowledgeInputState = {"query": "test query"}

        result = run_knowledge_node_in_graph(node, state)

        assert len(result["retrieved_docs"]) == 4

    @patch("aidev_agent.core.nodes.knowledge.KnowledgeRag")
    def test_get_query_priority(self, mock_rag_class, mock_llm, mock_knowledge_settings):
        """测试 get_query 的优先级: query > input > messages"""
        mock_rag_instance = MagicMock()
        mock_rag_instance.retrieve.return_value = create_mock_retrieve_result()
        mock_rag_class.return_value = mock_rag_instance

        node = AidevKnowledgeNode(llm=mock_llm, knowledge_query_options=mock_knowledge_settings)

        # 测试 query 优先级最高
        state: KnowledgeInputState = {
            "query": "query_value",
            "input": "input_value",
            "messages": [HumanMessage(content="message_value")],
        }

        run_knowledge_node_in_graph(node, state)

        call_args = mock_rag_instance.retrieve.call_args
        assert call_args[0][0] == "query_value"

    @patch("aidev_agent.core.nodes.knowledge.KnowledgeRag")
    @pytest.mark.parametrize(
        "content, expected",
        [
            (
                [
                    {"type": "image_url", "image_url": {"url": "https://example.com/test.png"}},
                    {"type": "text", "text": "这张图片有什么内容?"},
                ],
                "这张图片有什么内容?",
            ),
            ([{"type": "image_url", "image_url": {"url": "https://example.com/test.png"}}], ""),
        ],
    )
    def test_get_query_normalizes_multimodal_content(
        self, mock_rag_class, mock_llm, mock_knowledge_settings, content, expected
    ):
        """测试多模态 content 会归一化为知识库可检索文本"""
        mock_rag_class.return_value = MagicMock()
        node = AidevKnowledgeNode(llm=mock_llm, knowledge_query_options=mock_knowledge_settings)

        assert node.get_query({"messages": [HumanMessage(content=content)]}) == expected

    @patch("aidev_agent.core.nodes.knowledge.KnowledgeRag")
    def test_get_query_stringifies_non_text_query_dict(self, mock_rag_class, mock_llm, mock_knowledge_settings):
        """测试 query 字段传入非文本字典时会按通用归一化逻辑转为字符串。"""
        mock_rag_class.return_value = MagicMock()
        node = AidevKnowledgeNode(llm=mock_llm, knowledge_query_options=mock_knowledge_settings)

        query = [{"type": "image_url", "image_url": {"url": "https://example.com/test.png"}}]

        assert node.get_query({"query": query}) == ""

    @patch("aidev_agent.core.nodes.knowledge.KnowledgeRag")
    def test_empty_query_fallback(self, mock_rag_class, mock_llm, mock_knowledge_settings):
        """测试空查询回退"""
        mock_rag_instance = MagicMock()
        mock_rag_instance.retrieve.return_value = create_mock_retrieve_result()
        mock_rag_class.return_value = mock_rag_instance

        node = AidevKnowledgeNode(llm=mock_llm, knowledge_query_options=mock_knowledge_settings)

        # 空 state
        state: KnowledgeInputState = {}

        run_knowledge_node_in_graph(node, state)

        call_args = mock_rag_instance.retrieve.call_args
        # 应该返回空字符串
        assert call_args[0][0] == ""
