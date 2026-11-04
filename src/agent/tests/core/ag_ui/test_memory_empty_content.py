"""记忆来源检查不得改变空内容的既有展示和推理回退行为。"""

import pytest
from aidev_agent.core.ag_ui.event_builders import build_model_end_payload
from langchain_core.messages import AIMessage


@pytest.mark.parametrize("content", ["", []])
@pytest.mark.parametrize("reasoning", [None, "Provider reasoning answer"])
def test_empty_model_content_preserves_reasoning_fallback(content, reasoning):
    message = AIMessage(
        id="empty-model-response",
        content=content,
        additional_kwargs={"reasoning_content": reasoning} if reasoning else {},
        response_metadata={"memory_source_complete": True},
    )
    result = build_model_end_payload(message, {})
    assert result["content"] == (reasoning or "")
    assert result["memory_source_complete"] is False
