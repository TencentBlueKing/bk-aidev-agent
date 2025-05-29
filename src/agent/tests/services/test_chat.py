import json

import pytest
from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.config import settings
from aidev_agent.core.extend.agent.qa import CommonQAAgent
from aidev_agent.core.extend.models.llm_gateway import ChatModel
from aidev_agent.services.chat import ChatCompletionAgent, ExecuteKwargs
from aidev_agent.services.pydantic_models import (
    AgentOptions,
    ChatPrompt,
    FineGrainedScoreType,
    IntentRecognition,
    KnowledgebaseSettings,
)
from langchain_core.messages.ai import AIMessage
from langchain_core.messages.human import HumanMessage


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


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
def test_CommonQAAgent_chat_streaming():
    # 设置chat_model实例
    chat_model = ChatModel.get_setup_instance(
        # model="hunyuan-turbo",
        # model="gpt-4o",
        # model="gpt-4o-mini",
        # model="deepseek-v3",
        model="deepseek-r1",
        # model="deepseek-r1-14b",
        # model="deepseek-r1-32b",
        # model="deepseek-r1-70b",
        streaming=True,
    )

    # 设置kb_model实例
    kb_model = ChatModel.get_setup_instance(
        model="hunyuan-turbo",
        streaming=True,
    )

    # 获取客户端对象
    client = BKAidevApi.get_client_by_username(username="")

    # 设置工具
    tool_codes = ["weather-query"]
    tools = [client.construct_tool(tool_code) for tool_code in tool_codes]

    # 获取代理执行器和配置
    chat_history = [HumanMessage(content="你好"), AIMessage(content="你好，请问有什么可以帮您？")]
    agent_options = AgentOptions(
        intent_recognition_options=IntentRecognition(
            force_process_by_agent=False,
            role_prompt="",
        ),
        knowledge_query_options=KnowledgebaseSettings(
            knowledge_base_ids=[58],
            knowledge_item_ids=[10805],
            qa_response_kb_ids=[254],
            knowledge_resource_reject_threshold=(0.001, 0.1),
            topk=10,
            knowledge_resource_fine_grained_score_type=FineGrainedScoreType.LLM.value,
            use_general_knowledge_on_miss=False,
            rejection_response="抱歉，我无法回答你的问题。",
        ),
    )
    agent_e, cfg = CommonQAAgent.get_agent_executor(
        chat_model,
        kb_model,
        extra_tools=tools,
        chat_history=chat_history,
        agent_options=agent_options,
    )

    # 测试部分
    test_case_inputs = {"input": "云桌面绿屏解决方法"}

    for each in agent_e.agent.stream_standard_event(agent_e, cfg, test_case_inputs, timeout=2):
        if each == "data: [DONE]\n\n":
            break
        if each:
            chunk = json.loads(each[6:])
            print(f"\n=====> {chunk}\n")  # 方便跟其他标准输出区分开来
