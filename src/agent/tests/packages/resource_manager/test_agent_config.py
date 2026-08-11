"""``BaseResourceManager.get_agent_config`` 契约测试。

覆盖：
- 每次调用都打到 ``retrieve_agent_config``（SDK 不做进程内缓存）；
- ``version`` 透传到 ``retrieve_agent_config``；
- 装配规则：``prompt_setting`` → ``model_context_options_data``，``knowledgebase_settings`` + ``intent_recognition`` → ``knowledge_query_options_data``；
- 完整平台数据端到端验证（collection / user_define 两种 prompt 类型）；
- ``retrieve_agent_config`` 抛错时统一包裹为 ``ValueError``；
- ``related_agents`` 从 API 响应顶层字段读取（而非 conversation_settings.commands）；
- ``related_agents`` 中的 ``description``/``api_url`` 字段被正确映射；
- ``command_agent_mapping`` 仍从 ``conversation_settings.commands`` 读取；
- ``related_agents`` 为空列表或缺失时 ``AgentConfig.related_agents`` 为空列表。
"""

from __future__ import annotations

from typing import Optional

import pytest
from aidev_agent.packages.resource_manager.base import BaseResourceManager
from aidev_agent.pydantic_models import KnowledgeSettings, ModelContextSettings


def _build_raw(**overrides) -> dict:
    """构造最小可用的平台原始数据，通过 overrides 覆盖任意字段。"""
    raw = {
        "agent_name": "Test Agent",
        "prompt_setting": {
            "llm_code": "test-model",
            "non_thinking_llm": "test-non-thinking-model",
            "content": [{"role": "system", "content": "Test role prompt"}],
        },
        "related_tools": ["tool1", "tool2"],
        "conversation_settings": {
            "opening_remark": "Hello!",
            "commands": [
                {"id": 1, "agent_code": "cmd_child_1", "agent_name": "Cmd Child 1"},
                {"id": 2, "agent_code": "cmd_child_2", "agent_name": "Cmd Child 2"},
            ],
        },
        "related_agents": [
            {
                "agent_code": "ra_child_1",
                "agent_name": "RA Child 1",
                "description": "desc1",
                "api_url": "http://ra1.example.com",
            },
            {"agent_code": "ra_child_2", "agent_name": "RA Child 2", "description": "", "api_url": ""},
        ],
        "intent_recognition": {},
        "knowledgebase_settings": {"knowledgebases": []},
    }
    raw.update(overrides)
    return raw


def _build_full_raw(prompt_type: str = "collection", **overrides) -> dict:
    """构造包含完整平台字段的原始数据，模拟真实 API 返回。"""
    if prompt_type == "collection":
        content = [{"role": "hidden-system", "content": "你是一个翻译助手"}]
        collection_id = 4
        collection_variables: list | None = []
        prompt_content = None
    else:
        content = [{"role": "system", "content": "你是一个通用助手"}]
        collection_id = None
        collection_variables = None
        prompt_content = content

    raw = {
        "agent_name": "Full Test Agent",
        "conversation_settings": {
            "opening_remark": "",
            "predefined_questions": [],
            "commands": [],
            "enable_chat_session": True,
            "enable_word_selection_popup": False,
        },
        "prompt_setting": {
            "prompt_type": prompt_type,
            "prompt_content": prompt_content,
            "collection_id": collection_id,
            "collection_content": content,
            "collection_variables": collection_variables,
            "content": content,
            "llm_code": "test-llm-v1",
            "non_thinking_llm": "test-llm-lite",
            "temperature": 0.7,
            "context_window": 16,
            "llm_token_limit": 28000,
            "max_tokens": 20480,
            "tool_output_compress_thrd": 20480,
            "support_upload": {"vision": False},
        },
        "intent_recognition": {
            "knowledges": [],
            "topk": 10,
            "llm_code": "",
            "agent_type": "test-agent-type",
        },
        "knowledgebase_settings": {
            "knowledgebases": [1, 2],
            "retriever_code": "default_retriever",
            "query_function": "semantic",
            "document_fragment_count": 0,
            "knowledge_resource_fine_grained_score_type": "LLM",
            "knowledge_resource_reject_threshold": [0.5, 0.68],
            "independent_query_mode": "REWRITE",
            "polish": False,
            "origin": True,
            "knowledge_template_id": 1,
            "is_response_when_no_knowledgebase_match": True,
            "rejection_message": "",
        },
        "related_tools": ["tool-a", "tool-b"],
        "related_skills": [],
        "mcp_server_config": {"mcpServers": {}},
    }
    raw.update(overrides)
    return raw


class _StubResourceManager(BaseResourceManager):
    """覆盖 ``retrieve_agent_config`` 以避开 HTTP；不实现 ``get_client``。"""

    def __init__(self, raw_factory=None, raise_exc: Exception | None = None):
        super().__init__(app_code="x", app_secret="y")
        self.raw_factory = raw_factory or (lambda agent_code, version: _build_raw())
        self.call_count = 0
        self.last_version: Optional[str] = None
        self._raise_exc = raise_exc

    def retrieve_agent_config(self, agent_code: str, version: Optional[str] = None, **kwargs) -> dict:
        self.call_count += 1
        self.last_version = version
        if self._raise_exc is not None:
            raise self._raise_exc
        return self.raw_factory(agent_code, version)


# ---------------------------------------------------------------------------
# 基础契约测试
# ---------------------------------------------------------------------------


def test_get_agent_config_calls_retrieve_each_time():
    rm = _StubResourceManager()
    cfg1 = rm.get_agent_config("a1")
    cfg2 = rm.get_agent_config("a1")
    assert rm.call_count == 2
    assert cfg1 is not cfg2
    assert cfg1.agent_code == "a1"
    assert cfg2.agent_code == "a1"


@pytest.mark.parametrize("version", ["v2", None])
def test_version_passthrough(version):
    rm = _StubResourceManager()
    rm.get_agent_config("agent", version=version)
    assert rm.last_version == version


def test_default_rejection_message_when_kb_unmatched():
    """``rejection_message`` 未传入时由 Pydantic 默认值兜底。"""
    rm = _StubResourceManager()
    cfg = rm.get_agent_config("a")
    kb_settings = KnowledgeSettings.model_validate(cfg.knowledge_query_options_data)
    assert kb_settings.rejection_message
    assert "无法" in kb_settings.rejection_message


def test_model_context_options_data_assembled():
    """``prompt_setting`` 复制到 ``model_context_options_data``，``intent_recognition.agent_type`` → ``llm_code_agent_type``。"""
    raw = _build_raw()
    raw["prompt_setting"].update({"llm_token_limit": 12345, "tool_output_compress_thrd": 999})
    raw["intent_recognition"] = {"agent_type": "deepseek_r1"}
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("a")
    assert cfg.model_context_options_data["llm_token_limit"] == 12345
    assert cfg.model_context_options_data["tool_output_compress_thrd"] == 999
    assert cfg.model_context_options_data["llm_code_agent_type"] == "deepseek_r1"


def test_retrieve_failure_wrapped_as_value_error():
    rm = _StubResourceManager(raise_exc=RuntimeError("boom"))
    with pytest.raises(ValueError, match="Failed to retrieve agent config"):
        rm.get_agent_config("a")


# ============== related_agents 数据源测试 (Phase 21) ==============


def test_related_agents_from_top_level_field():
    """related_agents 从 API 响应顶层 related_agents 读取，而非 conversation_settings.commands。"""
    rm = _StubResourceManager()
    cfg = rm.get_agent_config("a")
    # related_agents 应来自顶层 related_agents，不是 commands
    assert len(cfg.related_agents) == 2
    assert cfg.related_agents[0]["agent_code"] == "ra_child_1"
    assert cfg.related_agents[1]["agent_code"] == "ra_child_2"


def test_related_agents_description_and_api_url_mapped():
    """related_agents 中的 description 和 api_url 字段被正确映射。"""
    rm = _StubResourceManager()
    cfg = rm.get_agent_config("a")
    assert cfg.related_agents[0]["description"] == "desc1"
    assert cfg.related_agents[0]["api_url"] == "http://ra1.example.com"
    assert cfg.related_agents[1]["description"] == ""
    assert cfg.related_agents[1]["api_url"] == ""


def test_command_agent_mapping_from_conversation_settings_commands():
    """command_agent_mapping 仍从 conversation_settings.commands 读取。"""
    rm = _StubResourceManager()
    cfg = rm.get_agent_config("a")
    assert cfg.command_agent_mapping == {1: "cmd_child_1", 2: "cmd_child_2"}


def test_related_agents_empty_list_when_empty_and_no_commands():
    """related_agents 和 commands 均为空时 AgentConfig.related_agents 为空列表。"""
    raw = _build_raw(related_agents=[], conversation_settings={"commands": []})
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("a")
    assert cfg.related_agents == []


def test_related_agents_empty_list_when_missing_and_no_commands():
    """related_agents 缺失且 commands 为空时 AgentConfig.related_agents 为空列表。"""
    raw = _build_raw(conversation_settings={"commands": []})
    raw.pop("related_agents", None)
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("a")
    assert cfg.related_agents == []


def test_related_agents_empty_when_top_level_empty():
    """related_agents 顶层字段为空时不再回退到 commands（该行为已废弃）。"""
    raw = _build_raw(related_agents=[])
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("a")
    assert cfg.related_agents == []


def test_related_agents_filters_empty_agent_code():
    """related_agents 中 agent_code 为空的条目被过滤。"""
    raw = _build_raw(
        related_agents=[
            {"agent_code": "valid_code", "agent_name": "Valid", "description": "", "api_url": ""},
            {"agent_code": "", "agent_name": "Empty", "description": "", "api_url": ""},
        ]
    )
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("a")
    assert len(cfg.related_agents) == 1
    assert cfg.related_agents[0]["agent_code"] == "valid_code"


# ---------------------------------------------------------------------------
# 完整平台数据端到端测试
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt_type, expected_role",
    [("collection", "hidden-system"), ("user_define", "system")],
)
def test_basic_fields_from_full_data(prompt_type, expected_role):
    """基本字段映射：agent_code / agent_name / chat_model / non_thinking_llm / role_prompts"""
    raw = _build_full_raw(prompt_type=prompt_type)
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("test-agent")

    assert cfg.agent_code == "test-agent"
    assert cfg.agent_name == "Full Test Agent"
    assert cfg.chat_model == "test-llm-v1"
    assert cfg.non_thinking_llm == "test-llm-lite"
    assert cfg.agent_options is None
    assert cfg.role_prompts is not None
    assert cfg.role_prompts[0]["role"] == expected_role


@pytest.mark.parametrize("prompt_type", ["collection", "user_define"])
def test_model_context_options_data_from_full_data(prompt_type):
    """model_context_options_data 是 prompt_setting 的副本 + llm_code_agent_type"""
    raw = _build_full_raw(prompt_type=prompt_type)
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("test-agent")

    # prompt_setting 中的字段应该完整保留
    assert cfg.model_context_options_data["llm_code"] == "test-llm-v1"
    assert cfg.model_context_options_data["non_thinking_llm"] == "test-llm-lite"
    assert cfg.model_context_options_data["llm_token_limit"] == 28000
    assert cfg.model_context_options_data["tool_output_compress_thrd"] == 20480
    assert cfg.model_context_options_data["temperature"] == 0.7
    assert cfg.model_context_options_data["max_tokens"] == 20480

    # intent_recognition.agent_type → llm_code_agent_type
    assert cfg.model_context_options_data["llm_code_agent_type"] == "test-agent-type"

    # 可正确构建 ModelContextSettings
    mcs = ModelContextSettings.model_validate(cfg.model_context_options_data)
    assert mcs.llm_token_limit == 28000
    assert mcs.tool_output_compress_thrd == 20480
    assert mcs.llm_code_agent_type == "test-agent-type"


@pytest.mark.parametrize("prompt_type", ["collection", "user_define"])
def test_knowledge_query_options_data_from_full_data(prompt_type):
    """knowledge_query_options_data 来自 knowledgebase_settings，可正确构建 KnowledgeSettings"""
    raw = _build_full_raw(prompt_type=prompt_type)
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("test-agent")

    kb = KnowledgeSettings.model_validate(cfg.knowledge_query_options_data)
    assert cfg.knowledgebase_ids == [1, 2]
    assert kb.knowledge_resource_fine_grained_score_type.value == "LLM"
    assert kb.knowledge_resource_reject_threshold == (0.5, 0.68)
    assert kb.independent_query_mode.name == "REWRITE"
    assert kb.is_response_when_no_knowledgebase_match is True


@pytest.mark.parametrize("prompt_type", ["collection", "user_define"])
def test_tool_and_skill_fields_from_full_data(prompt_type):
    """tool_codes / related_skills / mcp_server_config 映射"""
    raw = _build_full_raw(prompt_type=prompt_type)
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("test-agent")

    assert cfg.tool_codes == ["tool-a", "tool-b"]
    assert cfg.related_skills == []
    assert cfg.mcp_server_config == {}


@pytest.mark.parametrize("prompt_type", ["collection", "user_define"])
def test_conversation_and_hyperparams_from_full_data(prompt_type):
    """opening_mark / command_agent_mapping / temperature / max_tokens"""
    raw = _build_full_raw(prompt_type=prompt_type)
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("test-agent")

    assert cfg.opening_mark == ""
    assert cfg.command_agent_mapping == {}
    assert cfg.temperature == 0.7
    assert cfg.max_tokens == 20480


def test_knowledge_query_options_data_merges_intent_recognition():
    """intent_recognition 中的知识检索字段应合并到 knowledge_query_options_data"""
    raw = _build_raw()
    raw["intent_recognition"] = {
        "agent_type": "test-type",
        "with_index_specific_search_init": True,
        "with_index_specific_search_translation": False,
        "with_index_specific_search_keywords": True,
    }
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("a")

    assert cfg.knowledge_query_options_data["with_index_specific_search_init"] is True
    assert cfg.knowledge_query_options_data["with_index_specific_search_translation"] is False
    assert cfg.knowledge_query_options_data["with_index_specific_search_keywords"] is True


def test_model_context_options_data_no_agent_type():
    """intent_recognition 中无 agent_type 时，model_context_options_data 不含 llm_code_agent_type"""
    raw = _build_raw()
    raw["intent_recognition"] = {"knowledges": [], "topk": 10}
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("a")
    assert "llm_code_agent_type" not in cfg.model_context_options_data


def test_document_fragment_count_overrides_rough_recall_topk():
    """平台字段 document_fragment_count 应映射为运行时实际使用的 rough_recall_topk，并修复旧字段冲突。"""
    raw = _build_raw(
        knowledgebase_settings={
            "knowledgebases": [],
            "document_fragment_count": 3,
            "knowledge_resource_rough_recall_topk": 99,
        }
    )
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("a")

    assert cfg.knowledge_query_options_data["knowledge_resource_rough_recall_topk"] == 3
    assert "document_fragment_count" not in cfg.knowledge_query_options_data


@pytest.mark.parametrize(
    "prompt_fast_llm, expected",
    [
        ("fast-model", "fast-model"),
    ],
)
def test_fast_llm_from_prompt_setting(prompt_fast_llm, expected):
    """``get_agent_config`` 返回的 ``fast_llm`` 直接取 ``prompt_setting.fast_llm``，无回退。"""
    raw = _build_raw(
        prompt_setting={
            "llm_code": "llm-code",
            "non_thinking_llm": "non-thinking",
            "fast_llm": prompt_fast_llm,
        }
    )
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("a")
    assert cfg.fast_llm == expected


def test_fast_llm_none_is_preserved():
    """``prompt_setting.fast_llm`` 为 None 时保持未配置语义。"""
    raw = _build_raw(
        prompt_setting={
            "llm_code": "llm-code",
            "non_thinking_llm": "non-thinking",
            "fast_llm": None,
        }
    )
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    assert rm.get_agent_config("a").fast_llm is None


@pytest.mark.parametrize(
    "bkai_fast_llm, prompt_fast_llm, expected",
    [
        ("env-fast", "platform-fast", "env-fast"),
        ("env-fast", None, "env-fast"),
        (None, "platform-fast", "platform-fast"),
        ("", "platform-fast", "platform-fast"),
    ],
)
def test_fast_llm_env_override(monkeypatch, bkai_fast_llm, prompt_fast_llm, expected):
    """``BKAI_FAST_LLM`` 环境变量有值时覆盖平台 ``prompt_setting.fast_llm``。"""
    monkeypatch.setattr("aidev_agent.config.settings.BKAI_FAST_LLM", bkai_fast_llm)
    raw = _build_raw(
        prompt_setting={
            "llm_code": "llm-code",
            "non_thinking_llm": "non-thinking",
            "fast_llm": prompt_fast_llm,
        }
    )
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("a")
    assert cfg.fast_llm == expected


@pytest.mark.parametrize(
    "bkai_enable, prompt_enable, expected",
    [
        (True, False, True),
        (False, True, False),
        (None, True, True),
        (None, False, False),
    ],
)
def test_enable_judge_response_env_override(monkeypatch, bkai_enable, prompt_enable, expected):
    """``BKAI_ENABLE_JUDGE_RESPONSE`` 非 None 时覆盖 ``model_context_options_data``。"""
    monkeypatch.setattr("aidev_agent.config.settings.BKAI_ENABLE_JUDGE_RESPONSE", bkai_enable)
    raw = _build_raw(
        prompt_setting={
            "llm_code": "llm-code",
            "non_thinking_llm": "non-thinking",
            "fast_llm": "fast-model",
            "enable_judge_response": prompt_enable,
        }
    )
    rm = _StubResourceManager(raw_factory=lambda *_: raw)
    cfg = rm.get_agent_config("a")
    assert cfg.model_context_options_data["enable_judge_response"] == expected
