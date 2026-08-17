from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aidev_agent.packages.langchain_core.retrievers import multimodal
from aidev_agent.packages.langchain_core.retrievers.kb_rag import KnowledgeRag
from aidev_agent.pydantic_models import KnowledgeSettings


def _query(text: str = "") -> list[dict]:
    content = [{"type": "image_url", "image_url": {"url": "https://example.com/image.png"}}]
    if text:
        content.insert(0, {"type": "text", "text": text})
    return content


@pytest.mark.parametrize("query, expected", [("纯文本", "纯文本"), (_query("纯文本"), "纯文本"), (_query(), "")])
def test_build_multimodal_query_keeps_text_fallback_when_model_disabled(query, expected):
    assert multimodal.build_multimodal_query_for_search(query, model=None) == expected


@pytest.mark.parametrize(
    "query, expected",
    [
        (_query(), "架构图摘要"),
        (_query("如何部署"), "如何部署\n图片信息：摘要：架构图摘要\n描述：节点 A 连接节点 B"),
    ],
)
def test_build_multimodal_query_composes_image_text(mocker, query, expected):
    llm = MagicMock()
    llm.invoke.return_value = SimpleNamespace(content="摘要：架构图摘要\n描述：节点 A 连接节点 B")
    mocker.patch.object(multimodal, "_build_multimodal_query_llm", return_value=llm)

    result = multimodal.build_multimodal_query_for_search(query, model="qwen-vl")

    assert result == expected
    assert llm.invoke.call_args.args[0][0].content[1]["image_url"]["url"] == "https://example.com/image.png"


@pytest.mark.parametrize(
    "image_url",
    ["file:///etc/passwd", "ftp://example.com/a.png", "data:text/plain;base64,QQ==", "data:image/png;base64,bad"],
)
def test_extract_query_image_urls_rejects_unsupported_sources(image_url):
    query = [{"type": "image_url", "image_url": {"url": image_url}}]

    assert multimodal.extract_query_image_urls(query) == []


def test_extract_query_image_urls_accepts_valid_data_uri():
    image_url = "data:image/png;base64,aW1hZ2U="

    assert multimodal.extract_query_image_urls([{"type": "image_url", "image_url": {"url": image_url}}]) == [image_url]


def test_build_multimodal_query_llm_disables_thinking(mocker, monkeypatch):
    get_model = mocker.patch.object(multimodal.ChatModel, "get_setup_instance")
    monkeypatch.setenv("KNOWLEDGE_MULTIMODAL_QUERY_TIMEOUT_SECONDS", "12")

    multimodal._build_multimodal_query_llm("qwen3-6-35B-A3B")

    get_model.assert_called_once_with(
        model="qwen3-6-35B-A3B",
        temperature=0,
        max_retries=2,
        timeout=12.0,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


def test_knowledge_rag_uses_enriched_multimodal_query(mocker):
    retriever = MagicMock()
    retriever.search_knowledge_index_specific.return_value = []
    mocker.patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.dispatch_rag_event_chunk")
    image_llm = MagicMock()
    image_llm.invoke.return_value = SimpleNamespace(content="摘要：架构图摘要\n描述：节点 A 连接节点 B")
    mocker.patch.object(multimodal, "_build_multimodal_query_llm", return_value=image_llm)
    settings = KnowledgeSettings(
        knowledge_items=[{"id": 1}],
        with_index_specific_search_init=False,
        multimodal_query_model="qwen-vl",
    )

    KnowledgeRag(llm=MagicMock(), kb_retriever=retriever).retrieve("原文本", settings, input=_query("原文本"))

    assert (
        retriever.search_knowledge_index_specific.call_args.kwargs["query"]
        == "原文本\n图片信息：摘要：架构图摘要\n描述：节点 A 连接节点 B"
    )
