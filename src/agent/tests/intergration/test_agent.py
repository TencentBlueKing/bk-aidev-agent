import json

import pytest
from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.config import settings
from aidev_agent.core.extend.agent.qa import CommonQAAgent
from aidev_agent.core.extend.models.llm_gateway import ChatModel
from aidev_agent.services.pydantic_models import (
    AgentOptions,
    FineGrainedScoreType,
    IntentRecognition,
    KnowledgebaseSettings,
)
from langchain_core.callbacks.stdout import StdOutCallbackHandler


def verify_results(results: list[dict], need_reference_doc: bool = False) -> bool:
    has_reference_doc = not need_reference_doc
    for each in results:
        if "documents" in each:
            has_reference_doc = True
            assert each["cover"] is True
        else:
            assert "content" in each

    assert has_reference_doc


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
class TestStructedAgent:
    def test_CommonQAAgent_case_hunyuan(self):
        # 设置chat_model实例
        model_name = "deepseek-r1"
        chat_model = ChatModel.get_setup_instance(
            model=model_name,
            streaming=True,
        )

        # 获取客户端对象
        client = BKAidevApi.get_client_by_username(username="")
        # 设置工具
        tool_codes = [
            "list-user-business-cloudstone",
            "fix-file-md5",
            "list-task",
            "describe-task-log",
            "check-src-cos",
            "check-target-cos",
            "check-ftp",
            "check-version",
            "sync-cos-to-ftp",
            "sync-ftp-to-ver",
            "get-sync-job-log",
            "verify-ftp-whitelist",
            "update-ftp-info",
            "get-ftp-info",
        ]
        tools = [client.construct_tool(tool_code) for tool_code in tool_codes]
        knowledge_bases = [client.api.appspace_retrieve_knowledgebase(path_params={"id": 263})["data"]]
        role_prompt = """
        此外，必须记住当前用户(bk_username)是reynalddeng，这是你查询用户权限的唯一凭据！
        非常重要！如果要为GET请求生成action_input, 必须为每个参数带上"query__"前缀；如果要为POST请求生成action_input, 必须为每个参数带上"body__"前缀。
        非常重要！你的回答必须用markdown格式，在回答跟任务异常或报错相关的问题时，至少包含三个同层级的标题：现象分析、根因分析、解决方案，缺一不可！在此基础上可以新增次级标题。
        非常重要！用户没有权限直接接触版本机，绝对不要展示任何命令行操作！
        非常重要！绝对不要给用户展示调用工具的参数和代码，用户不知道怎么用！只需要告诉用户你能做什么，需要什么参数！
        非常重要！回答内容必须严格限制在知识库中已有的内容，绝对不能超出知识库范围！
        """

        # 获取代理执行器和配置
        agent_options = AgentOptions(
            intent_recognition_options=IntentRecognition(tool_output_compress_thrd=5000),
            knowledge_query_options=KnowledgebaseSettings(
                knowledge_bases=knowledge_bases,
                knowledge_resource_reject_threshold=(0.001, 0.1),
                topk=10,
                knowledge_resource_fine_grained_score_type=FineGrainedScoreType.LLM.value,
            ),
        )
        agent_e, cfg = CommonQAAgent.get_agent_executor(
            chat_model,
            chat_model,
            extra_tools=tools,
            role_prompt=role_prompt,
            agent_options=agent_options,
            callbacks=[StdOutCallbackHandler()],
        )

        # 测试部分
        test_case_inputs = {"input": "标准运维找不到文件。"}
        results = []
        for each in agent_e.agent.stream_standard_event(agent_e, cfg, test_case_inputs, timeout=2):
            if each == "data: [DONE]\n\n":
                break
            if each:
                chunk = json.loads(each[6:])
                results.append(chunk)

        verify_results(results)
