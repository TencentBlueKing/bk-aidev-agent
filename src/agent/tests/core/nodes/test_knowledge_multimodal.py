from unittest.mock import MagicMock

from aidev_agent.core.nodes.knowledge import AidevKnowledgeNode
from aidev_agent.pydantic_models import KnowledgeSettings
from langchain_core.messages import HumanMessage


def test_knowledge_node_preserves_raw_multimodal_input_for_retriever():
    content = [
        {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}},
        {"type": "text", "text": "这是什么"},
    ]
    node = AidevKnowledgeNode(llm=MagicMock(), knowledge_query_options=KnowledgeSettings())

    assert node.get_query_input({"messages": [HumanMessage(content=content)]}) == content
    assert node.get_query({"messages": [HumanMessage(content=content)]}) == "这是什么"
