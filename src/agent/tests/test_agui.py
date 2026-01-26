import pytest
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.types import RunAgentInput
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.services.common_agent import CommonQAAgent
from langchain_community.tools import ShellTool
from langgraph.checkpoint.memory import InMemorySaver
from loguru import logger


@pytest.mark.asyncio
@pytest.mark.slow
async def test_agui_graph_live(live_llm):
    agent_e, cfg = CommonQAAgent.get_agent_executor(
        llm=live_llm,
        knowledge_llm=None,
        extra_tools=[ShellTool()],
        chat_history=None,
        agent_options=None,
        checkpointer=InMemorySaver(),
    )
    body = {
        "thread_id": "1",
        "run_id": "2",
        "state": {},
        "messages": [
            {
                "id": "1",
                "role": "user",
                "content": "你是谁?",
                "name": "user",
            }
        ],
        "tools": [],
        "context": [],
        "forwardedProps": {},
        "additionalProp1": {},
    }

    agui_entry = AidevAGUIAgent(name="test_agui_agent", graph=agent_e)
    agent_input = RunAgentInput(**body)
    async for each in agui_entry.run(agent_input):
        pass


@pytest.mark.asyncio
async def test_graph():
    llm = ChatModel.get_setup_instance(model_name="qwen3")
    agent, cfg = CommonQAAgent().get_agent_executor(llm=llm, knowledge_llm=None)
    async for i in agent.astream_events({"input": "hello"}):
        logger.info(i)
