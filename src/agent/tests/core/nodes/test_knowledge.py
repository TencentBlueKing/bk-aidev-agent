# -*- coding: utf-8 -*-
"""
测试 knowledge.py 功能
"""

from unittest.mock import MagicMock, patch

from aidev_agent.core.nodes.knowledge import (
    AgentKnowledgeNode,
    AidevKnowledgeNode,
    KnowledgeInputState,
    filter_and_select_topk,
    make_knowledge_node,
)
from aidev_agent.enums import Decision
from aidev_agent.services.pydantic_models import AgentOptions
from langchain_core.messages import HumanMessage
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


def create_mock_llm():
    """创建 mock 的 LLM"""
    mock_llm = MagicMock()
    mock_llm.invoke = MagicMock(return_value=MagicMock(content="mocked response"))
    return mock_llm


def create_mock_agent_options():
    """创建 mock 的 AgentOptions"""
    return AgentOptions()


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
# 测试 filter_and_select_topk 函数
# ============================================================================


class TestFilterAndSelectTopk:
    """测试 filter_and_select_topk 函数"""

    def test_empty_docs(self):
        """测试空文档列表"""
        result = filter_and_select_topk([])
        assert result == []

    def test_no_filter_no_limit(self):
        """测试不过滤不限制数量"""
        docs = [
            {"metadata": {"fine_grained_score": 0.8}},
            {"metadata": {"fine_grained_score": 0.5}},
            {"metadata": {"fine_grained_score": 0.9}},
        ]
        result = filter_and_select_topk(docs, score_threshold=None, topk=20)
        # 应该按分数降序排序
        assert len(result) == 3
        assert result[0]["metadata"]["fine_grained_score"] == 0.9
        assert result[1]["metadata"]["fine_grained_score"] == 0.8
        assert result[2]["metadata"]["fine_grained_score"] == 0.5

    def test_filter_by_threshold(self):
        """测试按分数阈值过滤"""
        docs = [
            {"metadata": {"fine_grained_score": 0.8}},
            {"metadata": {"fine_grained_score": 0.3}},
            {"metadata": {"fine_grained_score": 0.9}},
            {"metadata": {"fine_grained_score": 0.4}},
        ]
        result = filter_and_select_topk(docs, score_threshold=0.5, topk=20)
        assert len(result) == 2
        assert result[0]["metadata"]["fine_grained_score"] == 0.9
        assert result[1]["metadata"]["fine_grained_score"] == 0.8

    def test_topk_limit(self):
        """测试 topk 限制"""
        docs = [
            {"metadata": {"fine_grained_score": 0.8}},
            {"metadata": {"fine_grained_score": 0.5}},
            {"metadata": {"fine_grained_score": 0.9}},
            {"metadata": {"fine_grained_score": 0.7}},
        ]
        result = filter_and_select_topk(docs, score_threshold=None, topk=2)
        assert len(result) == 2
        assert result[0]["metadata"]["fine_grained_score"] == 0.9
        assert result[1]["metadata"]["fine_grained_score"] == 0.8

    def test_filter_and_topk_combined(self):
        """测试过滤和 topk 组合使用"""
        docs = [
            {"metadata": {"fine_grained_score": 0.9}},
            {"metadata": {"fine_grained_score": 0.8}},
            {"metadata": {"fine_grained_score": 0.7}},
            {"metadata": {"fine_grained_score": 0.3}},
        ]
        result = filter_and_select_topk(docs, score_threshold=0.5, topk=2)
        assert len(result) == 2
        assert result[0]["metadata"]["fine_grained_score"] == 0.9
        assert result[1]["metadata"]["fine_grained_score"] == 0.8

    def test_missing_metadata(self):
        """测试缺少 metadata 的文档"""
        docs = [
            {"metadata": {"fine_grained_score": 0.8}},
            {"other_field": "value"},  # 没有 metadata
            {"metadata": {}},  # metadata 中没有 fine_grained_score
        ]
        result = filter_and_select_topk(docs, score_threshold=None, topk=20)
        assert len(result) == 3
        # 没有分数的文档应该默认为 0，排在最后
        assert result[0]["metadata"]["fine_grained_score"] == 0.8


# ============================================================================
# 测试 AgentKnowledgeNode 在 Graph 中的执行
# ============================================================================


class TestAgentKnowledgeNodeInGraph:
    """测试 AgentKnowledgeNode 在 Graph 中的执行"""

    def test_returns_agent_knowledge_node(self):
        """测试 make_knowledge_node 返回 AgentKnowledgeNode 实例"""
        mock_llm = create_mock_llm()
        mock_options = create_mock_agent_options()

        node = make_knowledge_node(llm=mock_llm, agent_options=mock_options)

        assert isinstance(node, AgentKnowledgeNode)
        assert node.llm is mock_llm
        assert node.agent_options is mock_options
        # 测试返回的节点有 retriever 属性
        assert hasattr(node, "retriever")
        assert node.retriever is not None
        # 测试返回的节点有 kb_retriever 属性
        assert hasattr(node, "kb_retriever")
        assert node.kb_retriever is not None

    @patch("aidev_agent.core.nodes.knowledge.KnowledgeRag")
    @patch("aidev_agent.core.nodes.knowledge.dispatch_custom_event")
    def test_state_return_with_input(self, mock_dispatch, mock_rag_class):
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

        mock_llm = create_mock_llm()
        mock_options = create_mock_agent_options()
        node = AgentKnowledgeNode(llm=mock_llm, agent_options=mock_options)

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

    def test_init_with_params(self):
        """测试默认参数初始化"""
        mock_llm = create_mock_llm()
        mock_options = create_mock_agent_options()

        node = AidevKnowledgeNode(llm=mock_llm, agent_options=mock_options)

        assert node.score_threshold is None
        assert node.topk == 20
        # 测试自定义参数初始化
        node = AidevKnowledgeNode(
            llm=mock_llm,
            agent_options=mock_options,
            score_threshold=0.5,
            topk=10,
        )
        assert node.score_threshold == 0.5
        assert node.topk == 10

    @patch("aidev_agent.core.nodes.knowledge.KnowledgeRag")
    def test_call_returns_retrieved_docs(self, mock_rag_class):
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

        mock_llm = create_mock_llm()
        mock_options = create_mock_agent_options()
        node = AidevKnowledgeNode(
            llm=mock_llm,
            agent_options=mock_options,
            score_threshold=0.6,
            topk=10,
        )
        result = run_knowledge_node_in_graph(node, {"query": "test query"})

        # 验证 retrieved_docs 被正确过滤和排序
        assert "retrieved_docs" in result
        # score_threshold=0.6 应该过滤掉 0.5 的文档
        assert len(result["retrieved_docs"]) == 2
        assert result["retrieved_docs"][0]["metadata"]["fine_grained_score"] == 0.9
        assert result["retrieved_docs"][1]["metadata"]["fine_grained_score"] == 0.7

    @patch("aidev_agent.core.nodes.knowledge.KnowledgeRag")
    def test_call_with_topk_limit(self, mock_rag_class):
        """测试 __call__ 的 topk 限制"""
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

        mock_llm = create_mock_llm()
        mock_options = create_mock_agent_options()
        node = AidevKnowledgeNode(
            llm=mock_llm,
            agent_options=mock_options,
            topk=2,
        )

        state: KnowledgeInputState = {"query": "test query"}

        result = run_knowledge_node_in_graph(node, state)

        # 验证只返回 topk 个文档
        assert len(result["retrieved_docs"]) == 2

    @patch("aidev_agent.core.nodes.knowledge.KnowledgeRag")
    def test_get_query_priority(self, mock_rag_class):
        """测试 get_query 的优先级: query > input > messages"""
        mock_rag_instance = MagicMock()
        mock_rag_instance.retrieve.return_value = create_mock_retrieve_result()
        mock_rag_class.return_value = mock_rag_instance

        mock_llm = create_mock_llm()
        mock_options = create_mock_agent_options()
        node = AidevKnowledgeNode(llm=mock_llm, agent_options=mock_options)

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
    def test_empty_query_fallback(self, mock_rag_class):
        """测试空查询回退"""
        mock_rag_instance = MagicMock()
        mock_rag_instance.retrieve.return_value = create_mock_retrieve_result()
        mock_rag_class.return_value = mock_rag_instance

        mock_llm = create_mock_llm()
        mock_options = create_mock_agent_options()
        node = AidevKnowledgeNode(llm=mock_llm, agent_options=mock_options)

        # 空 state
        state: KnowledgeInputState = {}

        run_knowledge_node_in_graph(node, state)

        call_args = mock_rag_instance.retrieve.call_args
        # 应该返回空字符串
        assert call_args[0][0] == ""
