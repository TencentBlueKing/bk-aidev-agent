from typing import Any

from langchain_core.callbacks import dispatch_custom_event

from aidev_agent.core.ag_ui.types import CustomMessageType

HUNYUAN_SPECIFIC_RESPONSE = "很抱歉，我还未学习到如何回答这个问题的内容，暂时无法提供相关信息。"


def normalize_query_for_search(query: Any) -> str:
    """将多模态 content 归一化为知识库可检索文本。"""
    if query is None:
        return ""
    if isinstance(query, str):
        return query
    if isinstance(query, list):
        text_parts = []
        for item in query:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                item_type = item.get("type")
                text = item.get("text") or item.get("content")
                if (
                    item_type == "text"
                    and isinstance(text, str)
                    or item_type not in {"image_url", "input_image"}
                    and isinstance(text, str)
                ):
                    text_parts.append(text)
        return "\n".join(part for part in text_parts if part.strip())
    return str(query)


def dispatch_rag_event_chunk(message: str):
    """Dispatch rag event chunk

    Args:
        message (str): The message to dispatch
        config (RunnableConfig): The runnable configuration
    """
    if not message.endswith("\n"):
        message += "\n"
    dispatch_custom_event(
        CustomMessageType.KNOWLEDGE_RAG_TEXT_CONTENT.value,
        data={"chunk": {"content": message}},
    )
