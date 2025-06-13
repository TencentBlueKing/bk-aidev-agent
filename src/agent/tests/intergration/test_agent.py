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
from tests.intergration.constants import TEST_DEFAULT_MODEL
from tests.intergration.utilities import get_stream_result, verify_streaming_result_format


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
class TestStructedAgent:
    def test_CommonQAAgent_case_thinking(self):
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
                knowledge_resource_fine_grained_score_type=FineGrainedScoreType.LLM,
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
        verify_streaming_result_format(
            [each for each in agent_e.agent.stream_standard_event(agent_e, cfg, test_case_inputs, timeout=2)]
        )

    def test_CommonQAAgent_case_hunyuan(self):
        # 设置chat_model实例
        chat_model = ChatModel.get_setup_instance(
            model=TEST_DEFAULT_MODEL,
            streaming=True,
        )

        # 获取客户端对象
        client = BKAidevApi.get_client_by_username(username="")
        # 设置工具
        knowledge_bases = [client.api.appspace_retrieve_knowledgebase(path_params={"id": 263})["data"]]

        # 获取代理执行器和配置
        agent_options = AgentOptions(
            knowledge_query_options=KnowledgebaseSettings(
                knowledge_bases=knowledge_bases,
                knowledge_resource_reject_threshold=(0.001, 0.1),
                topk=10,
                knowledge_resource_fine_grained_score_type=FineGrainedScoreType.LLM,
            ),
        )
        agent_e, cfg = CommonQAAgent.get_agent_executor(
            chat_model,
            chat_model,
            agent_options=agent_options,
            callbacks=[StdOutCallbackHandler()],
        )

        # 测试部分
        test_case_inputs = {"input": "标准运维找不到文件。"}
        # 特意将timeout弄长一些,用于跳过LOAD_MESSAGE
        verify_streaming_result_format(
            [each for each in agent_e.agent.stream_standard_event(agent_e, cfg, test_case_inputs, timeout=10)]
        )

    def test_CommonQAAgent_case_hunyuan_reject(self):
        # 设置chat_model实例
        chat_model = ChatModel.get_setup_instance(
            model=TEST_DEFAULT_MODEL,
            streaming=True,
        )

        # 获取客户端对象
        client = BKAidevApi.get_client_by_username(username="")
        # 设置工具
        knowledge_bases = [client.api.appspace_retrieve_knowledgebase(path_params={"id": 263})["data"]]

        # 获取代理执行器和配置
        agent_options = AgentOptions(
            knowledge_query_options=KnowledgebaseSettings(
                knowledge_bases=knowledge_bases,
                knowledge_resource_reject_threshold=(0.001, 0.1),
                topk=10,
                knowledge_resource_fine_grained_score_type=FineGrainedScoreType.LLM,
                is_response_when_no_knowledgebase_match=False,
                rejection_message="你在说啥呢?",
            ),
        )
        agent_e, cfg = CommonQAAgent.get_agent_executor(
            chat_model,
            chat_model,
            agent_options=agent_options,
            callbacks=[StdOutCallbackHandler()],
        )

        # 测试部分
        test_case_inputs = {"input": "谁是最可爱的人?"}
        # 特意将timeout弄长一些,用于跳过LOAD_MESSAGE
        results = [each for each in agent_e.agent.stream_standard_event(agent_e, cfg, test_case_inputs, timeout=10)]
        assert agent_options.knowledge_query_options.rejection_message in "".join(
            each["content"] for each in get_stream_result(results)
        )

    def test_knowledge_reject_threshold(self):
        """测试知识库拒绝阈值功能"""
        # 初始化模型和客户端
        model_name = "deepseek-r1"
        chat_model = ChatModel.get_setup_instance(
            model=model_name,
            streaming=True,
        )
        client = BKAidevApi.get_client_by_username(username="")
        knowledge_bases = [client.api.appspace_retrieve_knowledgebase(path_params={"id": 58})["data"]]

        # 配置代理使用特定阈值
        agent_options = AgentOptions(
            knowledge_query_options=KnowledgebaseSettings(
                knowledge_bases=knowledge_bases,
                knowledge_resource_reject_threshold=(0.95, 1.0),  # 设置高阈值
                topk=10,
                use_general_knowledge_on_miss=False,  # 设置为与知识库无关时拒答
                knowledge_resource_fine_grained_score_type=FineGrainedScoreType.EMBEDDING.value,
            ),
        )

        agent_e, cfg = CommonQAAgent.get_agent_executor(
            chat_model,
            chat_model,
            agent_options=agent_options,
            callbacks=[StdOutCallbackHandler()],
        )

        # 执行测试
        test_case_inputs = {"input": "云桌面绿屏怎么办"}
        results = []
        for each in agent_e.agent.stream_standard_event(agent_e, cfg, test_case_inputs, timeout=2):
            if each == "data: [DONE]\n\n":
                break
            if each:
                chunk = json.loads(each[6:])
                results.append(chunk)

        # 验证低相关性文档被拒绝
        has_documents = any("documents" in result for result in results)
        assert not has_documents, "当相关性低于阈值时应拒绝所有文档"

    def test_CommonQAAgent_case_thinking_case2(self):
        # 设置chat_model实例
        model_name = "deepseek-v3"
        chat_model = ChatModel.get_setup_instance(
            model=model_name,
            streaming=True,
        )

        # 获取客户端对象
        client = BKAidevApi.get_client_by_username(username="")
        # 设置工具
        tool_codes = ["weather-query"]
        tools = [client.construct_tool(tool_code) for tool_code in tool_codes]

        # 获取代理执行器和配置
        agent_options = AgentOptions(
            intent_recognition_options=IntentRecognition(tool_output_compress_thrd=5000),
            knowledge_query_options=KnowledgebaseSettings(
                knowledge_resource_reject_threshold=(0.001, 0.1),
                topk=10,
                knowledge_resource_fine_grained_score_type=FineGrainedScoreType.LLM,
            ),
        )
        agent_e, cfg = CommonQAAgent.get_agent_executor(
            chat_model,
            chat_model,
            extra_tools=tools,
            agent_options=agent_options,
            callbacks=[StdOutCallbackHandler()],
        )

        # 测试部分
        test_case_inputs = {"input": "今天深圳天气如何?"}
        results = [each for each in agent_e.agent.stream_standard_event(agent_e, cfg, test_case_inputs, timeout=2)]
        results = get_stream_result(results)
        assert not results[-2]["content"].endswith("```")
