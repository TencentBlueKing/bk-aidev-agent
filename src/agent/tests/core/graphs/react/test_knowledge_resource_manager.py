from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.pydantic_models import AgentExecutorKwargs, KnowledgeSettings
from langchain_core.messages import AIMessage, HumanMessage


class TestKnowledgeResourceManager:
    @pytest.fixture(autouse=True)
    def _disable_events_and_default_manager(self, mocker):
        mocker.patch("aidev_agent.core.nodes.knowledge.dispatch_custom_event")
        mocker.patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.dispatch_rag_event_chunk")
        self.default_manager = mocker.patch(
            "aidev_agent.packages.resource_manager.registry.resource_manager",
            side_effect=AssertionError("Knowledge retrieval must use the current resource manager"),
        )

    def _make_manager(self, scope):
        return SimpleNamespace(knowledge_query=Mock(return_value={"documents": [], "knowledge_content": [scope]}))

    def _make_retrieval(self, mode, manager):
        options = KnowledgeSettings(
            knowledge_bases=[{"id": 17}], enable_knowledge_node=True, enable_agentic_rag_tool=True
        )
        builder = (
            ReActAgentBuilder()
            .set_knowledge_llm(object())
            .set_bkai_options(AgentExecutorKwargs(resource_manager=manager, knowledge_query_options=options))
        )
        if mode == "node":
            node = builder._prepare_agent_knowledge_node(
                knowledge_llm=object(), knowledge_query_options=options, chat_history=[]
            )
            return lambda: node({"query": "question"}, {}, store=None)["knowledge_content"]
        tools = builder._prepare_agent_tools(langchain_middleware=())
        tool = next(tool for tool in tools if tool.name == "knowledge_retrieval")
        return lambda: tool.invoke({"query": "question"})

    @pytest.mark.parametrize("mode", ["node", "tool"])
    @pytest.mark.parametrize("concurrent", [False, True])
    def test_queries_keep_each_manager_when_agents_share_a_process(self, mode, concurrent):
        managers = [self._make_manager(scope) for scope in ("scope-a", "scope-b")]
        retrievals = [self._make_retrieval(mode, manager) for manager in managers] * 2
        if concurrent:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda retrieve: retrieve(), retrievals))
        else:
            results = [retrieve() for retrieve in retrievals]
        assert results == [["scope-a"], ["scope-b"]] * 2
        for manager in managers:
            assert manager.knowledge_query.call_count == 2
            assert manager.knowledge_query.call_args.args[0]["knowledge_base_id"] == [17]
        self.default_manager.assert_not_called()

    @pytest.mark.parametrize("mode", ["node", "tool"])
    def test_manager_errors_propagate_without_global_fallback_or_retry(self, mode):
        manager = self._make_manager("scope-a")
        manager.knowledge_query.side_effect = RuntimeError("query failed")
        retrieve = self._make_retrieval(mode, manager)
        with pytest.raises(RuntimeError, match="query failed"):
            retrieve()
        manager.knowledge_query.assert_called_once()
        self.default_manager.assert_not_called()

    @pytest.mark.parametrize("mode", ["node", "tool"])
    def test_builder_keeps_history_in_both_retrieval_paths(self, mode):
        manager = self._make_manager("scope-a")
        history = [HumanMessage(content="previous"), AIMessage(content="answer"), AIMessage(content="")]
        options = KnowledgeSettings(knowledge_bases=[{"id": 17}], enable_knowledge_node=True)
        builder = (
            ReActAgentBuilder()
            .set_knowledge_llm(object())
            .set_bkai_options(
                AgentExecutorKwargs(resource_manager=manager, knowledge_query_options=options, chat_history=history)
            )
        )
        if mode == "node":
            node = builder._prepare_agent_knowledge_node(
                knowledge_llm=object(), knowledge_query_options=options, chat_history=history
            )
            node({"query": "question"}, {}, store=None)
        else:
            tool = next(
                tool
                for tool in builder._prepare_agent_tools(langchain_middleware=())
                if tool.name == "knowledge_retrieval"
            )
            tool.invoke({"query": "question"})
        assert manager.knowledge_query.call_args.args[0]["chat_history"] == [
            {"role": "user", "content": "previous"},
            {"role": "assistant", "content": "answer"},
        ]
        self.default_manager.assert_not_called()
