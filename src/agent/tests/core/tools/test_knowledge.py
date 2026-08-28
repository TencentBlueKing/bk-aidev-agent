import json
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.config import settings
from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_agent.core.tools.knowledge import make_knowledge_retrieval_tool
from aidev_agent.packages.langchain_core.models import ChatModel
from aidev_agent.pydantic_models import KnowledgeSettings


@pytest.mark.skipif(
    not all([settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
@pytest.mark.slow
def test_knowledge_tool():
    llm = ChatModel.get_setup_instance(model="qwen3-235B")
    with open("tests/mock_data/knowledgebase.json") as fi:
        knowledgebase = json.load(fi)
    knowledge_settings = KnowledgeSettings(
        knowledge_bases=[knowledgebase], knowledge_resource_rough_recall_topk=2, raw=True
    )
    tool = make_knowledge_retrieval_tool(llm, knowledge_settings)
    result = tool.invoke(input={"query": "私有化部署deepseek"})
    print(result)


class TestMakeKnowledgeRetrievalTool:
    """知识库检索工具事件派发测试。"""

    def _make_tool(self):
        llm = object()
        knowledge_settings = KnowledgeSettings(knowledge_bases=[{"name": "kb"}])
        return make_knowledge_retrieval_tool(llm, knowledge_settings)

    def _patch_retriever(self, reference_doc):
        patcher_rag = patch("aidev_agent.core.tools.knowledge.KnowledgeRag")
        patcher_bk = patch("aidev_agent.core.tools.knowledge.BkRetriever")
        mock_rag = patcher_rag.start()
        patcher_bk.start()
        mock_rag.return_value.retrieve.return_value = {
            "knowledge_content": ["c1"],
            "reference_doc": reference_doc,
        }
        return patcher_rag, patcher_bk, mock_rag

    def test_knowledge_retrieval_dispatches_rag_events(self):
        reference_doc = [{"metadata": {"preview_path": "/p", "path": "/u", "display_name": "doc"}}]
        patcher_rag, patcher_bk, _ = self._patch_retriever(reference_doc)
        with patch("aidev_agent.core.tools.knowledge.dispatch_custom_event") as mock_dispatch:
            tool = self._make_tool()
            result = tool.invoke(input={"query": "..."}, config={"callbacks": [MagicMock()]})
        patcher_rag.stop()
        patcher_bk.stop()

        assert result == ["c1"]
        names = [call.args[0] for call in mock_dispatch.call_args_list]
        assert names == [
            CustomMessageType.KNOWLEDGE_RAG_START.value,
            CustomMessageType.KNOWLEDGE_RAG_RESULT.value,
            CustomMessageType.KNOWLEDGE_RAG_END.value,
        ]
        result_data = mock_dispatch.call_args_list[1].kwargs["data"]
        assert {"message_id", "data", "duration"} <= set(result_data.keys())
        assert result_data["data"] == [{"originFile": "/p", "url": "/u", "name": "doc"}]

    def test_knowledge_retrieval_no_config_skips_dispatch(self):
        patcher_rag, patcher_bk, _ = self._patch_retriever(
            [{"metadata": {"preview_path": "/p", "path": "/u", "display_name": "doc"}}]
        )
        with patch("aidev_agent.core.tools.knowledge.dispatch_custom_event") as mock_dispatch:
            tool = self._make_tool()
            result = tool.invoke({"query": "..."})
        patcher_rag.stop()
        patcher_bk.stop()

        assert result == ["c1"]
        mock_dispatch.assert_not_called()

    def test_knowledge_retrieval_dispatches_end_on_error(self):
        patcher_rag, patcher_bk, mock_rag = self._patch_retriever([])
        mock_rag.return_value.retrieve.side_effect = RuntimeError("kb timeout")
        with patch("aidev_agent.core.tools.knowledge.dispatch_custom_event") as mock_dispatch:
            tool = self._make_tool()
            with pytest.raises(RuntimeError, match="kb timeout"):
                tool.invoke(input={"query": "..."}, config={"callbacks": [MagicMock()]})
        patcher_rag.stop()
        patcher_bk.stop()

        names = [call.args[0] for call in mock_dispatch.call_args_list]
        assert names == [
            CustomMessageType.KNOWLEDGE_RAG_START.value,
            CustomMessageType.KNOWLEDGE_RAG_END.value,
        ]
