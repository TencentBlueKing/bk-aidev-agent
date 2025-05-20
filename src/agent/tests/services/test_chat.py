import pytest
from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.config import settings
from aidev_agent.core.extend.models.llm_gateway import ChatModel
from aidev_agent.services.chat import ChatCompletionAgent, ExecuteKwargs
from aidev_agent.services.pydantic_models import ChatPrompt


@pytest.fixture
def add_session():
    client = BKAidevApi.get_client()
    session_code = "onlyfortest1"
    client.api.create_chat_session(json={"session_code": session_code, "session_name": "testonly"})
    # 添加一些session content
    client.api.create_chat_session_content(
        json={
            "session_code": session_code,
            "role": "user",
            "content": "明天深圳天气怎么样?",
            "status": "success",
        }
    )
    yield session_code
    result = client.api.get_chat_session_contents(params={"session_code": session_code})
    for each in result.get("data", []):
        _id = each["id"]
        client.api.destroy_chat_session_content(path_params={"id": _id})
    client.api.destroy_chat_session(path_params={"session_code": session_code})


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
def test_common_agent_chat_streaming(add_session):
    llm = ChatModel.get_setup_instance(model="hunyuan-turbos")
    client = BKAidevApi.get_client()
    session_code = add_session
    knowledge_base_ids = [2]
    tool_codes = ["weather-query"]

    result = client.api.get_chat_session_context(path_params={"session_code": session_code})
    knowledge_bases = [
        client.api.appspace_retrieve_knowledgebase(path_params={"id": _id})["data"] for _id in knowledge_base_ids
    ]
    tools = [client.construct_tool(tool_code) for tool_code in tool_codes]

    agent = ChatCompletionAgent(
        chat_model=llm,
        chat_history=[ChatPrompt.model_validate(each) for each in result.get("data", [])],
        knowledge_bases=knowledge_bases,
        tools=tools,
    )
    for each in agent.execute(ExecuteKwargs(stream=True)):
        print(each)
