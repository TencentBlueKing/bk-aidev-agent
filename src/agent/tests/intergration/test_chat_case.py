"""测试聊天用例"""

import pytest
from aidev_agent.config import settings
from aidev_agent.core.extend.models.llm_gateway import ChatModel
from aidev_agent.services.chat import ChatCompletionAgent, ExecuteKwargs
from aidev_agent.services.pydantic_models import ChatPrompt
from tests.intergration.constants import TEST_DEFAULT_MODEL
from tests.intergration.utilities import verify_streaming_result_format


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
class TestChatCompletionAgent:
    def test_chat_completion_streaming(self, add_session):
        client, session_code = add_session
        # 添加一些session content
        client.api.create_chat_session_content(
            json={
                "session_code": session_code,
                "role": "user",
                "content": "您好,请问你是谁?",
                "status": "success",
            }
        )

        llm = ChatModel.get_setup_instance(model=TEST_DEFAULT_MODEL)
        result = client.api.get_chat_session_context(path_params={"session_code": session_code})
        agent = ChatCompletionAgent(
            chat_model=llm,
            chat_history=[ChatPrompt.model_validate(each) for each in result.get("data", [])],
        )
        verify_streaming_result_format([each for each in agent.execute(ExecuteKwargs(stream=True))])
