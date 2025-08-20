from asyncio import get_event_loop

from aidev_agent.core.extend.models.llm_gateway import ChatModel
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent


def test_one():
    client = MultiServerMCPClient(
        {
            "math": {
                "command": "python",
                "args": ["mcp_examples.py"],
                "transport": "stdio",
            },
        }
    )
    _loop = get_event_loop()
    tools = _loop.run_until_complete(client.get_tools())
    chat_model = ChatModel.get_setup_instance(model="hunyuan-turbos")
    agent = create_react_agent(chat_model, tools)
    math_response = _loop.run_until_complete(
        agent.ainvoke({"messages": [{"role": "user", "content": "what's (3 + 5) x 12?"}]})
    )
    assert math_response
