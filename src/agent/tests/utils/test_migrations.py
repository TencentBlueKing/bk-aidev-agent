from unittest.mock import patch

import pytest
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.pydantic_models import AgentOptions, IntentRecognition, KnowledgebaseSettings, KnowledgeSettings
from aidev_agent.utils.migrations import (
    migration_chat_model_non_thinking_from_non_thinking_llm_v1,
    migration_chat_session_context_from_chat_session_contents_v1,
    migration_knowledge_query_options_from_agent_options_v1,
    migration_model_context_options_from_agent_options_v1,
)


def test_migration_chat_model_non_thinking_from_non_thinking_llm_v1():
    migrated_model = MockChatModel(responses=["non-thinking"])

    with patch.object(ChatModel, "get_setup_instance", return_value=migrated_model) as mock_setup:
        result = migration_chat_model_non_thinking_from_non_thinking_llm_v1("legacy-lite")

    assert result is migrated_model
    mock_setup.assert_called_once_with(model="legacy-lite")
    assert migration_chat_model_non_thinking_from_non_thinking_llm_v1(None) is None


def test_migration_model_context_options_from_agent_options_v1():
    options = AgentOptions(
        intent_recognition_options=IntentRecognition(
            agent_type="deepseek_r1",
            tool_output_compress_thrd=4096,
        ),
        knowledge_query_options=KnowledgebaseSettings(llm_token_limit=28000),
    )

    migrated = migration_model_context_options_from_agent_options_v1(options)

    assert migrated.llm_code_agent_type == "deepseek_r1"
    assert migrated.tool_output_compress_thrd == 4096
    assert migrated.llm_token_limit == 28000


def test_migration_knowledge_query_options_from_agent_options_v1_maps_platform_document_fragment_count():
    options = AgentOptions(
        intent_recognition_options=IntentRecognition(
            with_index_specific_search_init=False,
            with_index_specific_search_translation=True,
            with_index_specific_search_keywords=True,
        ),
        knowledge_query_options=KnowledgebaseSettings(
            document_fragment_count=3,
            knowledge_resource_rough_recall_topk=99,
            rejection_message="",
        ),
    )

    migrated = migration_knowledge_query_options_from_agent_options_v1(options)

    assert isinstance(migrated, KnowledgeSettings)
    assert migrated.knowledge_resource_rough_recall_topk == 3
    assert migrated.with_index_specific_search_init is False
    assert migrated.with_index_specific_search_translation is True
    assert migrated.with_index_specific_search_keywords is True
    assert migrated.rejection_message == KnowledgeSettings().rejection_message


def test_migration_knowledge_query_options_from_agent_options_v1_keeps_rough_recall_when_document_fragment_count_zero():
    options = AgentOptions(
        knowledge_query_options=KnowledgebaseSettings(
            document_fragment_count=0,
            knowledge_resource_rough_recall_topk=7,
        )
    )

    migrated = migration_knowledge_query_options_from_agent_options_v1(options)

    assert migrated.knowledge_resource_rough_recall_topk == 7


def test_migration_knowledge_query_options_from_agent_options_v1_does_not_dump_default_rejection_message():
    options = AgentOptions(knowledge_query_options=KnowledgebaseSettings(document_fragment_count=5))

    migrated = migration_knowledge_query_options_from_agent_options_v1(options)

    assert migrated.knowledge_resource_rough_recall_topk == 5
    assert "rejection_message" not in options.knowledge_query_options.model_dump(exclude_unset=True)


@pytest.mark.parametrize(
    "rrf_weights",
    [
        {"dense": 1.0, "sparse": 0.0},
        {"dense": 0.0, "sparse": 1.0},
    ],
)
def test_legacy_knowledge_options_preserve_extreme_rrf_weights(rrf_weights):
    options = AgentOptions(knowledge_query_options=KnowledgebaseSettings(rrf_weights=rrf_weights))

    migrated = migration_knowledge_query_options_from_agent_options_v1(options)

    assert migrated.rrf_weights == rrf_weights


def test_legacy_knowledge_options_preserve_pure_scalar_retrieval_layers():
    options = AgentOptions(
        knowledge_query_options=KnowledgebaseSettings(
            recall_channels=[],
            scalar_expression='eq("status","enabled")',
        )
    )

    migrated = migration_knowledge_query_options_from_agent_options_v1(options)

    assert migrated.recall_channels == []
    assert migrated.scalar_expression == 'eq("status","enabled")'


def test_migration_chat_session_context_from_chat_session_contents_v1_skips_malformed_records():
    records = [
        {"id": "1", "role": "user", "content": "你好"},
        "not-a-dict",
        {"id": "2", "content": "缺 role"},
    ]

    result = migration_chat_session_context_from_chat_session_contents_v1(records)

    assert len(result) == 1
    assert result[0]["id"] == "1"
    assert result[0]["role"] == "user"


def test_migration_chat_session_context_from_chat_session_contents_v1_merges_builtin_property_base_without_none_override():
    record = {
        "id": "10",
        "role": "assistant",
        "content": "回答",
        "status": None,  # 平铺 None：不得遮蔽基底同名键
        "property": {
            "builtin_property": {"status": "complete", "message_id": "base-mid"},
            "artifacts": [{"name": "a.txt"}],
        },
    }

    result = migration_chat_session_context_from_chat_session_contents_v1([record])

    assert len(result) == 1
    bp = result[0]["builtin_property"]
    assert bp["status"] == "complete"  # 基底保留（平铺 None 未覆盖）
    assert bp["message_id"] == "base-mid"  # 基底独有键保留
    assert bp["artifacts"] == [{"name": "a.txt"}]  # 非 None 平铺键写入
