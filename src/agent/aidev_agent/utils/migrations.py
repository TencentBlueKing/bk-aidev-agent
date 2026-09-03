from __future__ import annotations

import logging
import uuid
from typing import Any, Mapping

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.pydantic_models import AgentOptions, KnowledgeSettings, ModelContextSettings

logger = logging.getLogger("aidev-agent")

_INDEX_SPECIFIC_SEARCH_KEYS = (
    "with_index_specific_search_init",
    "with_index_specific_search_translation",
    "with_index_specific_search_keywords",
)


def migration_chat_model_non_thinking_from_non_thinking_llm_v1(
    non_thinking_llm: str | None,
) -> BaseChatModel | None:
    """从旧版 ``non_thinking_llm`` 字符串迁移非思考模型实例。"""
    if non_thinking_llm:
        return ChatModel.get_setup_instance(model=non_thinking_llm)
    return None


def _dump_compat_options_part(value: Any) -> dict[str, Any]:
    """导出旧兼容模型中的显式输入值，避免默认值污染迁移结果。"""
    if value is None:
        return {}
    if isinstance(value, BaseModel):
        return {k: v for k, v in value.model_dump(exclude_unset=True).items() if v is not None}
    if isinstance(value, Mapping):
        return {k: v for k, v in value.items() if v is not None}
    return {}


def _split_agent_options(
    agent_options: AgentOptions | Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if agent_options is None:
        return {}, {}

    if isinstance(agent_options, AgentOptions):
        intent_options = agent_options.intent_recognition_options
        knowledge_options = agent_options.knowledge_query_options
    elif isinstance(agent_options, Mapping):
        intent_options = agent_options.get("intent_recognition_options") or agent_options.get("intent_recognition")
        knowledge_options = agent_options.get("knowledge_query_options") or agent_options.get("knowledgebase_settings")
    else:
        intent_options = getattr(agent_options, "intent_recognition_options", None)
        knowledge_options = getattr(agent_options, "knowledge_query_options", None)

    return _dump_compat_options_part(intent_options), _dump_compat_options_part(knowledge_options)


def migration_model_context_options_from_agent_options_v1(
    agent_options: AgentOptions | Mapping[str, Any] | None,
) -> ModelContextSettings:
    """从旧版 ``AgentOptions`` 迁移模型上下文配置。"""
    intent_options, knowledge_options = _split_agent_options(agent_options)
    data: dict[str, Any] = {}

    for key in ("llm_token_limit", "token_limit_margin"):
        if key in knowledge_options:
            data[key] = knowledge_options[key]

    if "tool_output_compress_thrd" in intent_options:
        data["tool_output_compress_thrd"] = intent_options["tool_output_compress_thrd"]
    if "llm_code_agent_type" in intent_options:
        data["llm_code_agent_type"] = intent_options["llm_code_agent_type"]
    elif "agent_type" in intent_options:
        data["llm_code_agent_type"] = intent_options["agent_type"]

    return ModelContextSettings.model_validate(data)


def migration_knowledge_query_options_from_agent_options_v1(
    agent_options: AgentOptions | Mapping[str, Any] | None,
) -> KnowledgeSettings:
    """从旧版 ``AgentOptions`` 迁移知识库检索配置。"""
    intent_options, knowledge_options = _split_agent_options(agent_options)
    data = dict(knowledge_options)

    # 平台字段为 document_fragment_count，aidev_agent 运行时实际读取 knowledge_resource_rough_recall_topk。
    # 旧版同时出现多个字段时，正数平台字段 document_fragment_count 优先，修复历史未转换导致配置不生效的问题。
    if "document_fragment_count" in data and data["document_fragment_count"] > 0:
        data["knowledge_resource_rough_recall_topk"] = data.pop("document_fragment_count")
        data.pop("topk", None)
    elif "knowledge_resource_rough_recall_topk" not in data and "topk" in data:
        data["knowledge_resource_rough_recall_topk"] = data.pop("topk")
    else:
        data.pop("topk", None)

    if data.get("rejection_message") == "":
        data.pop("rejection_message")

    for key in _INDEX_SPECIFIC_SEARCH_KEYS:
        if key in intent_options:
            data[key] = intent_options[key]

    return KnowledgeSettings.model_validate(data)


def migration_chat_session_context_from_chat_session_contents_v1(records: list[dict]) -> list[dict]:
    """把 get_chat_session_contents 返回 批量无损转换为 ChatPrompt 单账本形状。

    - 逐条经 ``_convert_chat_session_content_v1`` 转换，返回非 None 记录（批量容错内化）。
    - 逐条容错：非 dict / 缺 role 记录 warning 跳过，不打崩整批。
    """
    return [prompt for each in records if (prompt := _convert_chat_session_content_v1(each)) is not None]


def _convert_chat_session_content_v1(record: dict) -> dict | None:
    """把 get_chat_session_contents 获取的单条会话记录无损转换为 ChatPrompt 形状，供装配期作为单账本使用。

    - ``role``/``content`` 原样透传（非归一）。
    - ``property.extra`` → ChatPrompt ``extra`` 字段（含 command 等协议字段）。
    - 平铺顶层字段回嵌 ``builtin_property``
        - tool_calls/tool_call_id/duration/message_id/error/type/activity_type
        - convert 链读取的 turn_id/status/created_at/artifacts
        - property.builtin_property
      原有键为基底，非 None 平铺字段覆盖同名键, None 值不遮蔽基底
    - 其余原始顶层字段借 ``extra="allow"`` 透传为 ``__pydantic_extra__``，全程无损。
    - 逐条容错: record 非 dict 或缺 role 时 warning 并跳过（返回 None），避免畸形记录打崩整批。
    """
    if not isinstance(record, dict):
        logger.warning("migration_chat_session_context_from_chat_session_contents_v1: 跳过非 dict 记录 %r", record)
        return None
    role = record.get("role")
    if not role:
        logger.warning("migration_chat_session_context_from_chat_session_contents_v1: 跳过缺 role 记录 %r", record)
        return None

    property_data = record.get("property") or {}

    # 平铺顶层字段回嵌 builtin_property：property.builtin_property 为基底，非 None 平铺字段覆盖
    flat_fields = {
        "tool_calls": record.get("tool_calls"),
        "tool_call_id": record.get("tool_call_id"),
        "duration": record.get("duration"),
        "message_id": record.get("message_id"),
        "error": record.get("error"),
        "type": record.get("type"),
        "activity_type": record.get("activity_type"),
        "turn_id": property_data.get("turn_id"),
        "status": record.get("status"),
        "created_at": record.get("created_at"),
        "artifacts": property_data.get("artifacts"),
    }
    base = property_data.get("builtin_property") or {}
    builtin_property = {**base, **{k: v for k, v in flat_fields.items() if v is not None}}

    # 以原始记录为基底（全属性透传为 __pydantic_extra__），覆盖映射后的关键字段
    prompt = dict(record)
    prompt.update(
        {
            "id": str(record.get("id") or uuid.uuid4().hex),
            "role": role,
            "content": record.get("content"),
            "extra": property_data.get("extra"),
            "builtin_property": builtin_property,
        }
    )
    return prompt
