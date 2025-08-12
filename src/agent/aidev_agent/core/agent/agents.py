# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import json
import logging
from datetime import datetime
from typing import Callable, List, Optional, Sequence, Tuple, Union

import pydantic
import pytz
from langchain.agents.format_scratchpad.tools import format_to_tool_messages
from langchain.agents.output_parsers import JSONAgentOutputParser
from langchain.agents.output_parsers.tools import ToolsAgentOutputParser
from langchain.tools.render import render_text_description_and_args
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel, BaseLanguageModel
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers.json import parse_json_markdown
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_core.tools import BaseTool
from langchain_core.tools.render import ToolsRenderer

from aidev_agent.core.extend.intent.utils import (
    FINAL_ANSWER_PREFIXES,
    FINAL_ANSWER_SUFFIXES,
    is_deepseek_r1_series_models,
    remove_thinking_process,
)
from aidev_agent.services.pydantic_models import AgentOptions

MessageFormatter = Callable[[Sequence[Tuple[AgentAction, str]]], List[BaseMessage]]

logger = logging.getLogger(__name__)

OUTPUT_PARSER_ERR_MSG = "无法从 LLM 输出内容中解析出要求的 JSON BLOB，本次工具调用或结论解析失败。"
ACTION_INPUT_ERR_MSG = """要求LLM返回的 $JSON_BLOB 中的 $TOOL_INPUT 务必是个字典，
即务必同时指定参数名和参数值，而不要只指定参数值。但是LLM却只指定了其参数值，而没有指定参数名！工具调用失败！"""


def get_beijing_now():
    utc_now = datetime.now(pytz.utc)
    beijing_now = utc_now.astimezone(pytz.timezone("Asia/Shanghai")).strftime("%Y年%m月%d日 %H时%M分%S秒")
    return beijing_now


def enhanced_format_log_to_str(
    intermediate_steps: List[Tuple[AgentAction, str]],
    observation_prefix: str = "工具调用结果：",
    llm_prefix: str = "",
) -> str:
    """
    相比于 from langchain.agents.format_scratchpad import format_log_to_str 优化：
    1. 加强描述
    """
    thoughts = ""
    for action, observation in intermediate_steps:
        if observation in (OUTPUT_PARSER_ERR_MSG, ACTION_INPUT_ERR_MSG) or observation in [
            "Tool input validation error",
            "Tool execution error",
        ]:
            pass
            # TODO: 类似上述情况进行处理
        else:
            tried_tool = json.dumps({"action": action.tool, "action_input": action.tool_input}, ensure_ascii=False)
            thoughts += f"\n已经调用过的工具：\n{tried_tool}"
            thoughts += f"\n{observation_prefix}{observation}\n{llm_prefix}"
    return thoughts


class EnhancedJSONAgentOutputParser(JSONAgentOutputParser):
    """
    针对 deepseek r1 系列模型进行 parser 增强：
    1. 添加 remove_thinking_process 逻辑
    2. send_to_llm 改为 True （不过由于 enhanced_format_log_to_str 中的操作，目前实际没发送给 LLM）
    3. response["action_input"] 特殊情况的处理
    """

    llm: BaseChatModel = pydantic.Field(default=None)
    agent_options: Optional[AgentOptions] = pydantic.Field(default=None)

    def __init__(self, llm, agent_options: Optional[AgentOptions] = None):
        super().__init__()
        self.llm = llm
        if agent_options is not None:
            self.__class__.agent_options = agent_options

    def parse(self, text: str) -> Union[AgentAction, AgentFinish, List[AgentAction]]:
        if not text:
            raise RuntimeError("模型调用失败，LLM Gateway 返回的结果为空！")
        cur_time = datetime.now(pytz.utc).astimezone(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S %f")
        logger.info(f"=====> [text] [{cur_time}] {text}")
        response = None
        try:
            if is_deepseek_r1_series_models(self.llm):
                text = remove_thinking_process(text)
            response = parse_json_markdown(text)
            logger.info(f"=====> [response] [{cur_time}] {response}")

            # 处理并行工具调用
            if isinstance(response, list):
                agent_options = self.agent_options or getattr(self.__class__, "agent_options", None)
                if agent_options and agent_options.knowledge_query_options.enable_parallel_tool_calls:
                    # 当解析到JSON数组时，处理为并行工具调用，返回多个AgentAction对象
                    actions = []
                    for tool_call in response:
                        if tool_call["action"] == "Final Answer":
                            raise OutputParserException("Cannot mix Final Answer with tool calls in parallel mode")
                        if isinstance(tool_call.get("action_input"), str):
                            raise RuntimeError(ACTION_INPUT_ERR_MSG)
                        actions.append(AgentAction(tool_call["action"], tool_call.get("action_input", {}), text))
                    return actions
                else:
                    # gpt turbo frequently ignores the directive to emit a single action
                    logger.warning("Got multiple action responses: %s", response)
                    response = response[0]

            if response["action"] == "Final Answer":
                if isinstance(response["action_input"], dict):
                    # NOTE: 有时候这里不是字符串（例如用户query为“用json格式给我输出个不同排序算法的对比”）
                    # 这种情况下需要人工转一下，防止在langchain.memory.chat_memory.BaseChatMemory.save_context的以下代码中，
                    # 构建AIMessage的时候报错：
                    # ```
                    # self.chat_memory.add_messages(
                    #     [HumanMessage(content=input_str), AIMessage(content=output_str)]
                    # )
                    # ```
                    # 报错信息：
                    # ```
                    # pydantic.v1.error_wrappers.ValidationError: 2 validation errors for AIMessage
                    # content
                    # str type expected (type=type_error.str)
                    # content
                    # value is not a valid list (type=type_error.list)
                    # ```
                    response["action_input"] = json.dumps(response["action_input"], ensure_ascii=False, indent=4)
                return AgentFinish({"output": response["action_input"]}, text)
            else:
                if isinstance(response.get("action_input"), str):
                    # NOTE: aidev_agent.core.tool.base.ApiWrapper.__call__是这么定义的：
                    # ```
                    # def __call__(self, **kwargs) -> dict | str | bytes:
                    # ```
                    # 因此平台工具调用必须使用k-v对的形式，否则会报错：
                    # ```
                    # TypeError: ApiWrapper.__call__() takes 1 positional argument but 2 were given
                    # ```
                    # 因此这里加个校验：如果LLM没生成k-v对，action_input只生成了一个str，
                    # 但此处又不方便获取到该tool对应的真实参数定义是怎样的（否则可以手动构建成k-v对传给AgentAction），
                    # 因此这里给个错误提示，期待LLM下次能生成对。
                    raise RuntimeError(ACTION_INPUT_ERR_MSG)
                # TODO: 考虑是否使用 AgentActionMessageLog
                return AgentAction(response["action"], response.get("action_input", {}), text)
        except Exception as e:
            logger.warning(f"=====> [OutputParserException] [{cur_time}] {e}")

            # NOTE:
            # EnhancedJSONAgentOutputParser 中判断 final answer 的逻辑务必跟 stream_standard_event 中的保持一致！
            # 否则假设 stream_standard_event 通过前缀已经判断是 final answer 了，且通过正式结论的形式展示结论出来
            # 但是完整的 text 生成之后，如果 EnhancedJSONAgentOutputParser 这边完整地解析 final answer 发现有
            # Exception，则抛出异常，且继续进行下一个 action，则用户就会看到明明已经有 final answer 了
            # 但突然间又继续进行下一个 action 了，一直循环直到设定的上限。
            for final_answer_prefix, final_answer_suffix in zip(FINAL_ANSWER_PREFIXES, FINAL_ANSWER_SUFFIXES):
                if final_answer_prefix in text:
                    final_answer_content = text.split(final_answer_prefix)[-1][: -len(final_answer_suffix)]
                    return AgentFinish({"output": final_answer_content}, text)

            # 其余情况正常抛出 OutputParserException
            if str(e) == ACTION_INPUT_ERR_MSG:
                raise OutputParserException(
                    f"错误信息：{ACTION_INPUT_ERR_MSG}",
                    observation=ACTION_INPUT_ERR_MSG,
                    llm_output=f"LLM 输出内容为：“{text}”",
                    send_to_llm=True,
                ) from e
            else:
                raise OutputParserException(
                    "错误信息：无法从 LLM 输出内容中解析出所需的 JSON BLOB",
                    observation=OUTPUT_PARSER_ERR_MSG,
                    llm_output=f"LLM 输出内容为：“{text}”",
                    send_to_llm=True,
                ) from e


def create_enhanced_structured_chat_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: ChatPromptTemplate,
    agent_options: Optional[AgentOptions] = None,
    tools_renderer: ToolsRenderer = render_text_description_and_args,
    *,
    stop_sequence: Union[bool, List[str]] = False,
) -> Runnable:
    """
    相比于 langchain.agents.structured_chat.base.create_structured_chat_agent
    针对 deepseek r1 系列模型进行 parser 增强：
    1. 替换成 EnhancedJSONAgentOutputParser
    2. 增加提供当前北京时间信息 beijing_now 给 LLM
    3. stop_sequence 改成 False，因为目前不依赖observation，thought等进行循环
    """

    main_vars = {"tools", "tool_names", "agent_scratchpad"}

    # beijing_now 不是 prompt 中强制定义的
    if "beijing_now" in prompt.input_variables:
        main_vars.add("beijing_now")

    missing_vars = main_vars.difference(prompt.input_variables + list(prompt.partial_variables))
    if missing_vars:
        raise ValueError(f"Prompt missing required variables: {missing_vars}")

    prompt = prompt.partial(
        tools=tools_renderer(list(tools)),
        tool_names=", ".join([t.name for t in tools]),
    )

    if "beijing_now" in prompt.input_variables:
        main_vars.add("beijing_now")
        prompt = prompt.partial(
            beijing_now=get_beijing_now(),
        )

    if stop_sequence:
        stop = ["\nObservation"] if stop_sequence is True else stop_sequence
        llm_with_stop = llm.bind(stop=stop)
    else:
        llm_with_stop = llm

    agent = (
        RunnablePassthrough.assign(
            agent_scratchpad=lambda x: enhanced_format_log_to_str(x["intermediate_steps"]),
        )
        | prompt
        | llm_with_stop
        | EnhancedJSONAgentOutputParser(llm, agent_options)
    )
    return agent


def create_enhanced_tool_calling_agent(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt: ChatPromptTemplate,
    *,
    message_formatter: MessageFormatter = format_to_tool_messages,
) -> Runnable:
    """
    相比于 langchain.agents.tool_calling_agent.base.create_tool_calling_agent
    增强：
    1. 增加提供当前北京时间信息 beijing_now 给 LLM
    """

    main_vars = {"agent_scratchpad"}

    # beijing_now 不是 prompt 中强制定义的
    if "beijing_now" in prompt.input_variables:
        main_vars.add("beijing_now")

    missing_vars = main_vars.difference(prompt.input_variables + list(prompt.partial_variables))
    if missing_vars:
        raise ValueError(f"Prompt missing required variables: {missing_vars}")

    if "beijing_now" in prompt.input_variables:
        main_vars.add("beijing_now")
        prompt = prompt.partial(
            beijing_now=get_beijing_now(),
        )

    if tools:
        if not hasattr(llm, "bind_tools"):
            raise ValueError(
                "This function requires a .bind_tools method be implemented on the LLM.",
            )
        llm_with_tools = llm.bind_tools(tools)
    else:
        llm_with_tools = llm

    agent = (
        RunnablePassthrough.assign(agent_scratchpad=lambda x: message_formatter(x["intermediate_steps"]))
        | prompt
        | llm_with_tools
        | ToolsAgentOutputParser()
    )
    return agent
