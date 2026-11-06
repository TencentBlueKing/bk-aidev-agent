import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command, interrupt

from aidev_agent.core.ag_ui.reference_documents import (
    arrange_reference_history,
    keep_cited_documents,
    reference_documents_for_display,
)
from aidev_agent.core.ag_ui.types import ActivityMessage
from aidev_agent.core.citations import (
    CITATION_INSTRUCTION,
    CitationRegistry,
    citation_index,
    cite_knowledge,
    cited_numbers,
    renumber_citations,
    select_cited,
    uses_citations,
)
from aidev_agent.core.nodes.knowledge import AgentKnowledgeNode
from aidev_agent.core.nodes.model.context_assembly import ContextAssembly
from aidev_agent.core.nodes.model.node import build_model_node
from aidev_agent.core.nodes.model.pydantic_models import ModelNodeSettings, ProcessorContext
from aidev_agent.core.nodes.tool import build_tool_node
from aidev_agent.core.tools.a2a_tools.provider import AgentBackendResolver, _cite_child_result, get_agent_tools
from aidev_agent.core.tools.a2a_tools.types import AgentResult, AgentSpec, KnowledgeReference
from aidev_agent.core.tools.a2a_tools.utils import collect_knowledge_references
from aidev_agent.core.tools.knowledge import make_knowledge_retrieval_tool
from aidev_agent.pydantic_models import ChatPrompt, KnowledgeSettings
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.utils.migrations import migration_chat_session_context_from_chat_session_contents_v1

SOURCE = "https://example.com/source"
PREVIEW = "https://example.com/agent-develop/knowledgebase?knowledgeName=a.md"


def chunk(title, url):
    return f"文档标题：{title}\n来源链接：{url}\n\n{title} 正文"


def reference(title, path, preview=""):
    return {"metadata": {"display_name": title, "path": path, "preview_path": preview}}


def test_model_reads_numbered_sources_and_documents_carry_the_same_numbers():
    content, documents = cite_knowledge(
        [chunk("A", SOURCE), chunk("B", PREVIEW)],
        [reference("A", SOURCE, PREVIEW), reference("B", PREVIEW, PREVIEW)],
        CitationRegistry(),
    )
    assert content[0] == CITATION_INSTRUCTION
    assert content[1].startswith("引用编号：[1]\n文档标题：A")
    assert content[2].startswith("引用编号：[2]\n文档标题：B")
    assert documents == [
        {"originFile": PREVIEW, "url": SOURCE, "name": "A", "citation_index": 1},
        {"originFile": PREVIEW, "url": PREVIEW, "name": "B", "citation_index": 2},
    ]


def test_chunks_without_a_source_line_keep_the_previous_prompt_and_shape():
    content, documents = cite_knowledge(["plain"], [reference("A", SOURCE, PREVIEW)], CitationRegistry())
    assert content == ["plain"]
    assert documents == [{"originFile": PREVIEW, "url": SOURCE, "name": "A"}]


def test_repeated_retrievals_keep_stable_numbers_for_the_same_source():
    citations = CitationRegistry()
    cite_knowledge([chunk("A", SOURCE)], [reference("A", SOURCE)], citations)
    content, documents = cite_knowledge(
        [chunk("B", PREVIEW), chunk("A", SOURCE)], [reference("B", PREVIEW), reference("A", SOURCE)], citations
    )
    assert [document["citation_index"] for document in documents] == [2, 1]
    assert content[1].startswith("引用编号：[2]")
    assert content[2].startswith("引用编号：[1]")


def test_parallel_numbering_never_hands_out_one_number_twice():
    citations = CitationRegistry()
    with ThreadPoolExecutor(max_workers=8) as pool:
        numbers = list(pool.map(citations.number, [f"https://example.com/{index % 20}" for index in range(200)]))
    assert sorted(set(numbers)) == list(range(1, 21))


@pytest.mark.parametrize(
    "answer,expected",
    [("结论[2]，另见[1][2]", [1, 2]), ("只用了[3]", [3]), ("没有标注", None), ("编造[9]", None), (None, None)],
)
def test_select_cited_orders_by_number_and_returns_none_without_citations(answer, expected):
    items = [{"citation_index": 2}, {"citation_index": 1}, {"metadata": {"citation_index": 3}}, {"name": "plain"}]
    selected = select_cited(items, answer)
    numbers = (
        None
        if selected is None
        else [item.get("citation_index") or item["metadata"]["citation_index"] for item in selected]
    )
    assert numbers == expected


def test_renumber_rewrites_every_marker_once():
    assert renumber_citations("a[1] b[2][1] c[3]", {1: 2, 2: 1}) == "a[2] b[1][2] c[3]"
    assert renumber_citations("a[1]", {}) == "a[1]"


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("根据《共享Node优化报告》，内存下降。", [1]),
        ("参考 共享Node优化报告 的结论", [1]),
        ("参考《共享Node优化报告》，另一来源[2]", [2]),
        ("参考《共享Node优化报告》，编号无效[9]", [1]),
        ("参考《共享Node》", None),
        ("参考《共享Node优化报告补充版》", None),
        ("`《共享Node优化报告》`\n```\n《监控设计报告》\n```", None),
    ],
)
def test_title_fallback_prefers_valid_numbers_and_ignores_partial_or_code_mentions(answer, expected):
    documents = [saved("共享Node优化报告", 1), saved("监控设计报告", 2)]
    selected = select_cited(iter(documents), answer)
    assert ([citation_index(item) for item in selected] if selected else None) == expected


def test_title_fallback_rejects_ambiguous_titles():
    assert select_cited([saved("同名文档", 1), saved("同名文档", 2)], "根据《同名文档》") is None


def test_title_fallback_reads_display_metadata_and_preserves_snapshot_references():
    documents = reference_documents_for_display([saved("共享Node优化报告", 1), saved("监控设计报告", 2)])
    answer = "根据《共享Node优化报告》，内存下降。"
    arranged = arrange_reference_history([activity(1, documents), message(2, "assistant", answer)])
    assert arranged[0]["content"] == answer
    assert [citation_index(item) for item in arranged[1]["content"]] == [1]


@pytest.mark.parametrize("mode", [False, True])
@pytest.mark.parametrize("source", ["tool", "node", "child", "none"])
def test_model_prompt_includes_citation_policy_for_both_rag_modes_and_child_results(mode, source):
    tools = [MagicMock(name="retriever")] if source == "tool" else []
    if tools:
        tools[0].name = "knowledge_retrieval"
    state = {"knowledge_content": [CITATION_INSTRUCTION]} if source == "node" else {}
    if source == "child":
        state["messages"] = [ToolMessage(content='{"references":[{"citation_index":1}]}', tool_call_id="child")]
    assembly = ContextAssembly(tools=tools)
    with patch("aidev_agent.core.nodes.model.node.ContextAssembly", return_value=assembly):
        build_model_node(llm=MagicMock(), tools=tools, node_options=ModelNodeSettings(use_structured_response=mode))
    for _ in range(2):
        context = ProcessorContext(state=state, config={})
        template = assembly.get_chat_prompt_template(context)
        variables = dict.fromkeys(template.input_variables, "")
        variables["agent_scratchpad"] = [] if not mode else ""
        rendered = template.invoke(variables).to_messages()
        assert rendered[0].content.count(CITATION_INSTRUCTION) == (0 if source == "none" else 1)
        if not mode:
            assert isinstance(rendered[0], SystemMessage)


CODE_ANSWER = "用 `items[1]` 取值：\n```python\nprint(rows[2])\n```\n结论[3]"


def test_code_brackets_are_neither_citations_nor_rewritten():
    assert cited_numbers(CODE_ANSWER) == {3}
    assert cited_numbers("未闭合代码前[1]\n```\nrows[2]") == {1}
    assert select_cited([{"citation_index": 1}], "先看 `items[1]`") is None
    assert renumber_citations(CODE_ANSWER, {1: 7, 2: 8, 3: 9}) == CODE_ANSWER.replace("结论[3]", "结论[9]")


@pytest.mark.parametrize(
    "code",
    [
        "~~~python\nrows[1]\n~~~",
        "~~~~python\n~~~\nrows[1]\n~~~~",
        "````markdown\n```\nrows[1]\n````",
        "``a`rows[1]`b``",
        "`rows\n[1]`",
        "~~~python\nrows[1]",
        "> ~~~python\n> rows[1]\n> ~~~",
        "- ~~~python\n  rows[1]\n  ~~~",
        "    ~~~python\n    rows[1]\n    ~~~",
    ],
)
def test_markdown_code_spans_keep_array_indexes_during_child_citation_remapping(code):
    answer = f"结论[2]\n{code}"
    assert cited_numbers(answer) == {2}
    assert renumber_citations(answer, {1: 7, 2: 8}) == f"结论[8]\n{code}"


def test_inline_triple_backticks_do_not_hide_the_following_prose():
    answer = "```rows[1]```，结论[2]"
    assert cited_numbers(answer) == {2}
    assert renumber_citations(answer, {1: 7, 2: 8}) == "```rows[1]```，结论[8]"


def test_rebuilt_graph_restores_citation_numbers_after_checkpoint_resume():
    checkpointer = InMemorySaver()
    config = {"configurable": {"thread_id": "citation-resume"}}

    def tool_call(query):
        return AIMessage(
            content="", tool_calls=[{"name": "knowledge_retrieval", "args": {"query": query}, "id": query}]
        )

    def pause(state):
        interrupt("Continue retrieval?")
        return {"messages": [tool_call("B")]}

    def route(state):
        return "pause" if sum(isinstance(message, ToolMessage) for message in state["messages"]) == 1 else END

    def build_graph():
        tool = make_knowledge_retrieval_tool(
            object(), KnowledgeSettings(knowledge_bases=[{"name": "kb"}]), kb_retriever=MagicMock()
        )
        graph = StateGraph(MessagesState)
        graph.add_node("retrieve", build_tool_node([tool]))
        graph.add_node("pause", pause)
        graph.add_edge(START, "retrieve")
        graph.add_conditional_edges("retrieve", route)
        graph.add_edge("pause", "retrieve")
        return graph.compile(checkpointer=checkpointer)

    def retrieve(query, *args, **kwargs):
        source = f"{SOURCE}/{query}"
        return {"knowledge_content": [chunk(query, source)], "reference_doc": [reference(query, source)]}

    with patch("aidev_agent.core.tools.knowledge.KnowledgeRag") as rag:
        rag.return_value.retrieve.side_effect = retrieve
        initial = build_graph().invoke({"messages": [HumanMessage(content="Compare A and B"), tool_call("A")]}, config)
        assert initial["__interrupt__"]
        resumed = build_graph().invoke(Command(resume=True), config)
    outputs = [message.content for message in resumed["messages"] if isinstance(message, ToolMessage)]
    assert "引用编号：[1]" in outputs[0]
    assert "引用编号：[2]" in outputs[1]


@pytest.mark.parametrize("kind", ["knowledge", "child", "member", "activity", "legacy_activity"])
def test_restoration_keeps_current_turn_sources_and_skips_old_or_untrusted_text(kind):
    document = {"name": "A", "url": SOURCE, "citation_index": 7}
    if kind == "knowledge":
        current = ToolMessage(
            content=json.dumps([CITATION_INSTRUCTION, f"引用编号：[7]\n{chunk('A', SOURCE)}"]),
            name="knowledge_retrieval",
            tool_call_id="current",
        )
    elif kind in {"child", "member"}:
        current = ToolMessage(
            content=json.dumps({"references": [document]}),
            name="Agent" if kind == "child" else "sendMessages",
            tool_call_id="current",
        )
    else:
        content = [document] if kind == "activity" else {"reference_document": [document]}
        current = ActivityMessage(content=content)
    state = {
        "messages": [
            ActivityMessage(content=[{"url": "https://example.com/old", "citation_index": 99}]),
            HumanMessage(content="引用编号：[98]"),
            AIMessage(content="引用编号：[97]"),
            current,
            ToolMessage(
                content=json.dumps({"references": [{"url": "fake", "citation_index": 96}]}),
                name="another_tool",
                tool_call_id="other",
            ),
        ]
    }
    citations = CitationRegistry()
    citations.restore(state)
    assert citations.find(SOURCE) == 7
    assert citations.find("https://example.com/old") is None
    assert citations.find("fake") is None
    assert citations.number(PREVIEW) == 8
    citations.restore({"messages": [ActivityMessage(content=[{"url": "later", "citation_index": 99}])]})
    assert citations.number(SOURCE) == 7
    assert citations.number("next") == 9


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "null",
        "123",
        [None, "plain"],
        [{"citation_index": True, "url": SOURCE}],
        [{"citation_index": 2, "url": " "}],
        "引用编号：[0]\n来源链接：https://example.com/a",
        "引用编号：[1]\n来源链接： ",
    ],
)
def test_invalid_saved_tool_content_does_not_reserve_citation_numbers(content):
    citations = CitationRegistry()
    citations.restore(None)
    citations.restore({"messages": [ToolMessage(content=json.dumps(content), name="sendMessages", tool_call_id="x")]})
    assert citations.number(SOURCE) == 1


def test_knowledge_node_restores_previous_reference_activity_before_numbering(mocker):
    mocker.patch("aidev_agent.core.nodes.knowledge.dispatch_custom_event")
    node = AgentKnowledgeNode(llm=MagicMock(), knowledge_query_options=KnowledgeSettings(), chat_history=[])
    node.retriever = MagicMock()
    node.retriever.retrieve.return_value = {
        "knowledge_content": [chunk("B", PREVIEW)],
        "reference_doc": [reference("B", PREVIEW)],
    }
    result = node(
        {
            "messages": [
                HumanMessage(content="compare"),
                ActivityMessage(content=[{"url": SOURCE, "citation_index": 4}]),
            ]
        },
        {},
        store=None,
    )
    assert result["messages"][0].content[0]["citation_index"] == 5


@pytest.mark.parametrize("item", [None, "[1]", {"citation_index": True}, {"citation_index": 0}, {"metadata": "x"}])
def test_citation_index_ignores_values_that_are_not_citation_numbers(item):
    assert citation_index(item) is None


def test_child_sources_without_link_or_number_keep_markers_unchanged():
    citations = CitationRegistry()
    child = AgentResult(
        status="completed",
        result="结论[1]",
        references=(KnowledgeReference(name="no link"), KnowledgeReference(name="A", url=SOURCE)),
    )
    cited = _cite_child_result(child, citations)
    assert cited.result == "结论[1]"
    assert [reference.citation_index for reference in cited.references] == [None, 1]
    assert _cite_child_result(child, None) is child


def test_uses_citations_detects_numbered_knowledge_and_child_results():
    assert uses_citations({"knowledge_content": [CITATION_INSTRUCTION]})
    child = ToolMessage(content=json.dumps({"references": [{"citation_index": 1}]}), tool_call_id="call")
    assert uses_citations({"messages": [AIMessage(content="x"), child]})
    assert not uses_citations({"knowledge_content": ["plain"], "messages": [AIMessage(content="[1]")]})


def test_knowledge_tool_returns_numbered_content_and_dispatches_numbered_documents():
    citations = CitationRegistry()
    with (
        patch("aidev_agent.core.tools.knowledge.KnowledgeRag") as rag,
        patch("aidev_agent.core.tools.knowledge.dispatch_custom_event") as dispatch,
    ):
        rag.return_value.retrieve.return_value = {
            "knowledge_content": [chunk("A", SOURCE)],
            "reference_doc": [reference("A", SOURCE, PREVIEW)],
        }
        tool = make_knowledge_retrieval_tool(
            object(), KnowledgeSettings(knowledge_bases=[{"name": "kb"}]), kb_retriever=MagicMock(), citations=citations
        )
        assert set(tool.tool_call_schema.model_json_schema()["properties"]) == {"query"}
        result = tool.invoke(input={"query": "q"}, config={"callbacks": [MagicMock()]})
    assert result[0] == CITATION_INSTRUCTION and result[1].startswith("引用编号：[1]")
    assert dispatch.call_args_list[1].kwargs["data"]["data"][0]["citation_index"] == 1
    assert citations.find(SOURCE) == 1


def test_display_title_carries_the_number_while_metadata_keeps_the_bare_title():
    document = {"name": "A", "url": SOURCE, "originFile": PREVIEW, "citation_index": 2}
    once = reference_documents_for_display([document])
    assert once[0]["name"] == "[2] A"
    assert once[0]["metadata"]["display_name"] == "A"
    assert reference_documents_for_display(once) == once
    assert reference_documents_for_display([{**document, "citation_index": None}])[0]["name"] == "A"


def test_child_references_keep_their_number_through_collection():
    event = {"type": "CUSTOM", "name": "knowledge_rag_result"}
    value = reference_documents_for_display([{"name": "A", "url": SOURCE, "originFile": PREVIEW, "citation_index": 3}])
    references = collect_knowledge_references([{**event, "value": value}])
    assert references == [KnowledgeReference(name="A", url=SOURCE, preview_url=PREVIEW, citation_index=3)]
    assert "citation_index" not in KnowledgeReference(name="A", url=SOURCE).model_dump()


def test_child_sources_join_the_parent_numbers_and_markers_are_rewritten(mocker):
    citations = CitationRegistry()
    citations.number(PREVIEW)
    child = AgentResult(
        status="completed",
        result="结论[1]，补充[2]",
        references=(
            KnowledgeReference(name="A", url=SOURCE, preview_url="https://example.com/p/a", citation_index=1),
            KnowledgeReference(name="B", preview_url=PREVIEW, citation_index=2),
        ),
    )
    backend = mocker.Mock()
    backend.execute.return_value = child
    resolver = AgentBackendResolver().register("bkai", mocker.Mock(return_value=backend))
    spec = AgentSpec(name="child", description="test", backend_type="bkai")
    dispatch = mocker.patch("aidev_agent.core.tools.a2a_tools.provider.dispatch_custom_event")
    tool = get_agent_tools([spec], resolver, citations=citations)[0]
    result = json.loads(tool.func(agent_name="child", message="q", config={"callbacks": [object()]}, state={}))
    assert result["result"] == "结论[2]，补充[1]"
    assert [each["citation_index"] for each in result["references"]] == [2, 1]
    assert [each["citation_index"] for each in dispatch.call_args_list[1].kwargs["data"]["data"]] == [2, 1]


@pytest.mark.parametrize("tool_name", ["Agent", "sendMessages"])
def test_child_tools_continue_saved_parent_numbers_after_resume(mocker, tool_name):
    backend = mocker.Mock()
    backend.execute.return_value = AgentResult(
        status="completed",
        result="结论[1]",
        references=(KnowledgeReference(name="B", url=PREVIEW, citation_index=1),),
    )
    resolver = AgentBackendResolver().register("bkai", mocker.Mock(return_value=backend))
    spec = AgentSpec(name="child", description="test", backend_type="bkai")
    state = {
        "messages": [HumanMessage(content="compare"), ActivityMessage(content=[{"url": SOURCE, "citation_index": 3}])],
        "bk_agent_team": {"member": {"agent_name": "child", "session_code": "session"}},
    }
    tools = {tool.name: tool for tool in get_agent_tools([spec], resolver, citations=CitationRegistry())}
    arguments = {"agent_name": "child"} if tool_name == "Agent" else {"member_name": "member"}
    result = json.loads(tools[tool_name].func(**arguments, message="q", config={}, state=state))
    assert result["result"] == "结论[4]"
    assert result["references"][0]["citation_index"] == 4


def activity(message_id, documents):
    return {
        "id": message_id,
        "role": "activity",
        "status": "success",
        "content": documents,
        "activity_type": "reference_document",
        "property": {"builtin_property": {"type": "reference_document", "message_id": f"ref-{message_id}"}},
    }


def message(message_id, role, content):
    return {"id": message_id, "role": role, "content": content}


def saved(name, number=None):
    document = {"name": name, "url": f"https://example.com/{name}", "origin_file_url": ""}
    return {**document, "citation_index": number} if number else document


def test_snapshot_keeps_only_cited_documents_after_each_answer():
    records = [
        message("1", "user", "q1"),
        activity("2", [saved("a", 1), saved("b", 2)]),
        activity("3", [saved("c", 3)]),
        message("4", "assistant", "结论[2]"),
        message("5", "user", "q2"),
        activity("6", [saved("d", 1), saved("e", 2)]),
        message("7", "assistant", "没有标注"),
        message("8", "user", "q3"),
        activity("9", [saved("f"), saved("g")]),
        message("10", "assistant", "旧记录[1]"),
    ]
    session_context = migration_chat_session_context_from_chat_session_contents_v1(records)
    history = [ChatPrompt.model_validate(each) for each in session_context]
    agent = ChatCompletionAgent(chat_history=history)
    snapshot = agent._build_snapshot_agui_messages()
    assert [item["id"] for item in snapshot] == ["1", "4", "2", "5", "7", "6", "8", "10", "9"]
    names = {item["id"]: [each["name"] for each in item["content"]] for item in snapshot if item["role"] == "activity"}
    assert names == {"2": ["[2] b"], "6": ["[1] d", "[2] e"], "9": ["f", "g"]}
    assert len(agent.chat_history[1].content) == 2


def rag_activity(message_id, documents):
    return {
        "id": message_id,
        "role": "activity",
        "activity_type": "knowledge_rag",
        "content": {"content": "", "reference_document": documents},
    }


def test_history_lists_references_right_after_the_final_answer():
    records = [
        message("1", "user", "q"),
        rag_activity("2", [saved("a", 1), saved("b", 2)]),
        message("3", "assistant", "先查一下"),
        activity("4", []),
        message("5", "assistant", "结论[1]"),
        {"id": "6", "role": "interrupt", "content": {}},
    ]
    arranged = arrange_reference_history(records)
    assert [item["id"] for item in arranged] == ["1", "3", "4", "5", "2", "6"]
    assert [each["name"] for each in arranged[4]["content"]["reference_document"]] == ["[1] a"]


def test_turn_still_answering_keeps_its_order_and_documents():
    records = [
        message("1", "user", "q"),
        activity("2", [saved("a", 1)]),
        {"id": "3", "role": "reasoning", "content": "[1]"},
    ]
    arranged = arrange_reference_history(records)
    assert [item["id"] for item in arranged] == ["1", "2", "3"]
    assert arranged[1]["content"][0]["name"] == "[1] a"


def test_keep_cited_documents_leaves_other_activities_unchanged():
    content = {"artifacts": []}
    assert keep_cited_documents(content, "artifacts_generated", {1}) is content


def test_run_end_snapshot_is_sent_when_the_run_numbered_its_sources():
    resource_manager = MagicMock()
    resource_manager.get_chat_session_contents.return_value = [
        {"id": 1, "role": "user", "content": "q"},
        {"id": 2, "role": "assistant", "content": "结论[1]"},
    ]
    agent = ChatCompletionAgent(thread_id="session-1", resource_manager=resource_manager, executor_info={})
    snapshot = agent._build_run_end_snapshot_agui_messages({"knowledge_content": [CITATION_INSTRUCTION]})
    assert [item["id"] for item in snapshot] == ["1", "2"]
    assert agent._build_run_end_snapshot_agui_messages({"knowledge_content": ["plain"]}) is None
