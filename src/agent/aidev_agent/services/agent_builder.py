import logging

from aidev_agent.config import settings
from src.agent.aidev_agent.core.extend.agent.qa import CommonQAAgent
from src.agent.aidev_agent.core.extend.models.llm_gateway import ChatModel
from src.agent.aidev_agent.services.chat import ChatCompletionAgent
from src.agent.aidev_agent.services.pydantic_models import ChatPrompt
from src.agent.aidev_agent.utils.agent_config_manager import AgentConfigManager

logger = logging.getLogger("aidev_agent")


class AgentInstanceBuilder:
    @classmethod
    def build_agent_instance_by_session(cls, session_code, api_client, agent_code):
        """
        通过session_code初始化Agent实例
        :param session_code:    会话代码
        :param api_client:      API客户端实例
        :param agent_code:      Agent代码
        """
        logger.info(
            f"AgentInstanceBuilder: try to build agent instance for session_code->{session_code},use agent->{agent_code}"
        )
        session_context_data = api_client.api.get_chat_session_context(path_params={"session_code": session_code}).get(
            "data", []
        )
        logger.info(f"AgentInstanceBuilder: session->{session_code} get session_context_data->{session_context_data}")

        # 是否需要切换智能体
        switch_agent = False

        try:
            # 获取最后一条用户消息
            last_user_message = (
                next((msg for msg in reversed(session_context_data) if msg["role"] == "user"), None) or {}
            )

            command = last_user_message.get("extra", {}).get("command")

            if command:  # 若存在Command，且该Command映射到了新的Agent,那么在本轮对话中使用新的Agent的配置
                command_agent_code = settings.AIDEV_COMMAND_AGENT_MAPPING.get(command, agent_code)
                switch_agent = True if command_agent_code != agent_code else False
                agent_code = command_agent_code  # 切换Agent
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"AgentInstanceBuilder: get last user message error->{e}")

        if session_context_data and session_context_data[-1]["role"] == "assistant":
            logger.info(
                f"AgentInstanceBuilder: session->{session_code} last message->{session_context_data[-1]} is "
                f"assistant, remove it"
            )
            # TODO: 如果最后一条消息是assistant，且content里有"生成中"三个字，则去掉
            content = session_context_data[-1]["content"]
            if settings.AIDEV_AGENT_AI_GENERATING_KEYWORD in content:  # 只要 content 里有"生成中"三个字即可
                session_context_data.pop()

        agent = build_chat_completion_agent(
            api_client=api_client,
            agent_code=agent_code,
            session_context_data=session_context_data,
            switch_agent=switch_agent,
        )
        return agent


def build_chat_completion_agent(api_client, agent_code, session_context_data, switch_agent) -> ChatCompletionAgent:
    logger.info(f"AgentInstanceBuilder: try to build agent instance with agent_code->{agent_code}")
    config = AgentConfigManager.get_config(agent_code=agent_code, api_client=api_client)

    if switch_agent:  # 若需要切换Agent,则在【本轮对话】中替换System Prompt,并不会在平台侧落地
        logger.info(f"AgentInstanceBuilder: switch agent to->{agent_code}")
        # 找到最后一条role为system的记录并修改
        for item in reversed(session_context_data):
            if item["role"] == "system":
                item["content"] = config.role_prompt
                break  # 修改最后一条后就退出循环

    # 构造对话上下文历史
    chat_history = [ChatPrompt.model_validate(each) for each in session_context_data]

    auth_headers = {
        "bk_app_code": settings.APP_CODE,
        "bk_app_secret": settings.SECRET_KEY,
    }

    # LLM 网关地址
    llm_base_url = settings.LLM_GW_ENDPOINT

    llm = ChatModel.get_setup_instance(
        model=config.llm_model_name,
        base_url=llm_base_url,
        auth_headers=auth_headers,
    )

    knowledge_bases = [
        api_client.api.appspace_retrieve_knowledgebase(path_params={"id": _id})["data"]
        for _id in config.knowledgebase_ids
    ]
    knowledge_items = [
        api_client.api.appspace_retrieve_knowledge(path_params={"id": _id})["data"] for _id in config.knowledge_ids
    ]
    tools = [api_client.construct_tool(tool_code) for tool_code in config.tool_codes]

    # 可继承该方法并改造为通过Factory获取
    agent_cls = CommonQAAgent

    return ChatCompletionAgent(
        chat_model=llm,
        role_prompt=config.role_prompt,
        tools=tools,
        knowledge_bases=knowledge_bases,
        knowledge_items=knowledge_items,
        chat_history=chat_history,
        agent_cls=agent_cls,
    )
