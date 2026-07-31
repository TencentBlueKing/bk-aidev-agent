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

from __future__ import annotations

import enum
import json
import logging
import time
import traceback
from collections import defaultdict, deque
from copy import deepcopy
from typing import Any, Dict, Generator, Iterator, List, Optional, Tuple, TypedDict
from urllib.parse import parse_qs, urlparse

from langchain_core.messages import BaseMessageChunk, ToolMessage
from langchain_core.runnables.schema import StreamEvent
from typing_extensions import NotRequired

from aidev_agent.config import settings
from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_agent.enums import StreamEventType
from aidev_agent.utils import Empty
from aidev_agent.utils.async_utils import async_generator_with_timeout, async_to_sync_generator

logger = logging.getLogger(__name__)

OUTPUT_PARSER_ERR_MSG = "无法从 LLM 输出内容中解析出要求的 JSON BLOB，本次工具调用或结论解析失败。"
ACTION_INPUT_ERR_MSG = """要求LLM返回的 $JSON_BLOB 中的 $TOOL_INPUT 务必是个字典，
即务必同时指定参数名和参数值，而不要只指定参数值。但是LLM却只指定了其参数值，而没有指定参数名！工具调用失败！"""
FINAL_ANSWER_PREFIXES = [
    '```\n{\n  "action": "Final Answer",\n  "action_input": "',
    '```json\n{\n  "action": "Final Answer",\n  "action_input": "',
    """```\n{\n  \"action\": \"Final Answer\",\n  \"action_input\": \"""",
    """```json\n{\n  \"action\": \"Final Answer\",\n  \"action_input\": \"""",
    '```json\\n\\n{\n  \\"action\\": \\"Final Answer\\",\n  \\"action_input\\": \\"',
    """```json\n{\n  \"action\": \"Final Answer\",\n  \"action_input\": \"""",
    # 匹配 "action_input" 的值为 {...} 的情况，例如用户问“用json格式给我输出不同排序算法的对比”
    """```json\n{\n  "action": "Final Answer",\n  "action_input": """,
    '{\n  "action": "Final Answer",\n  "action_input": "',
]
FINAL_ANSWER_SUFFIXES = [
    '"\n}\n```',
    '"\n}\n```',
    """\"\n}\n```""",
    """\"\n}\n```""",
    '\\"\n}\\n\\n```',
    """\"\n}\n```""",
    "\n}\n```",
    '"\n}',
]


class BKAiStreamingAgentType(enum.Enum):
    """BK 前端流交互协议 - Think 类型"""

    StructuredChatCommonQAAgent = "StructuredChatCommonQAAgent"
    ToolCallingCommonQAAgent = "ToolCallingCommonQAAgent"


class BkAiStreamEvent(TypedDict):
    """前端流事件数据结构"""

    event: StreamEventType
    content: NotRequired[str]
    cover: NotRequired[bool]
    elapsed_time: NotRequired[float]
    code: NotRequired[int]
    message: NotRequired[str]
    documents: NotRequired[Any]


class BkAiStreamingProtocol:
    """BK 前端流交互协议"""

    LOADING_AGENT_MESSAGE: str = "正在思考..."
    think_symbols: List[str] = [
        "<think>\n",
        "\n</think>\n",  # 不要用"\n</think>\n\n"，留个"\n"以让后续```前面带"\n"，方便用markdown语法渲染
    ]
    final_answer_prefixes: List[str] = deepcopy(FINAL_ANSWER_PREFIXES)
    final_answer_suffixes: List[str] = deepcopy(FINAL_ANSWER_SUFFIXES)
    # NOTE: 人工定义结束标志，用于去除 final_answer_suffix 时往后判断是否已经到达末尾
    # 这是因为 Final Answer 内部本身可能刚好有 final_answer_suffix 这种模式，直接过滤有误删风险。
    # 因此使用缓冲队列，往后读到结束标志，再进行以下剔除操作。
    end_content = "<｜end▁of▁sentence｜>"

    def __init__(
        self,
        timeout: int = 30,
        skip_thought: bool = False,
        max_cache_length: int = 50,
        max_tool_output_len: int = 500,
        agent_type: BKAiStreamingAgentType = BKAiStreamingAgentType.ToolCallingCommonQAAgent,
    ):
        """初始化适配器

        Args:
            timeout: 流超时时间（秒）
            skip_thought: 是否跳过思考过程
            max_cache_length: 最大缓存大小
        """
        self.timeout = timeout
        self.skip_thought = skip_thought
        self.max_cache_length = max_cache_length

        # 运行时状态
        self.run_info: defaultdict[str, dict] = defaultdict(dict)
        self.final_result: str = ""
        self.non_think_content: str = ""
        self.cache: deque[BkAiStreamEvent] = deque(maxlen=max_cache_length)
        self.agent_think_start_time: float = 0.0

        # 状态标志
        self.first_chunk = True
        self.last_ret_is_empty = False
        self.front_end_display = True
        self.first_triple_backticks = True
        self.has_custom_event = False

        self.agent_type = agent_type
        # StructuredChatCommonQAAgent 特有状态
        self.last_event_type = None
        self.final_answer_prefix_to_filter = None
        self.final_answer_suffix_to_filter = None
        self.cur_event_type = StreamEventType.THINK
        self.final_answer_occurred = False
        self.first_time_final_answer = True
        self.first_think_event = True
        self.final_answer_suffix = ""
        # ToolCallingCommonQAAgent 特有状态
        self.force_think_content = False
        self.has_reasoning_content = False
        self.has_tool_call = False
        self.first_tool_args = True
        self.tool_calling = False
        self.max_tool_output_len = max_tool_output_len

    def common_filter(self, cache, filter_symbols, event_type: StreamEventType) -> Tuple[bool, BkAiStreamEvent]:
        hit = False
        recall_event = None
        combined_content = "".join(
            [item["content"] for item in cache if "content" in item and item.get("event") == event_type]
        )
        for symbol in filter_symbols:
            if symbol in combined_content:
                # 如果是 final_answer_prefix 这种特殊情况，外层逻辑会补充一个 recall_ret 回来
                # 因此这里可以放心地从 think 中去除末尾的那个需要归属 text 的块
                if symbol in self.final_answer_prefixes and not combined_content.endswith(symbol):
                    start_index = combined_content.find(symbol)
                    combined_content = combined_content[:start_index]
                else:
                    combined_content = combined_content.replace(symbol, "")
                hit = True
                break
        if hit:
            if combined_content:
                recall_event = BkAiStreamEvent(event=event_type, content=combined_content, cover=False)
            # think 类型有个特殊处理：需要保证在最后一个 think event 上带上 elapsed_time
            if event_type == StreamEventType.THINK:
                for item in cache:
                    if elapsed_time := item.get("elapsed_time"):
                        if recall_event:
                            recall_event["elapsed_time"] = elapsed_time
                        else:
                            recall_event = BkAiStreamEvent(
                                event=event_type,
                                content="",
                                cover=False,
                                elapsed_time=elapsed_time,
                            )
                        break
        return hit, recall_event

    def cache_filter(self, final_answer_prefix_to_filter=None, final_answer_suffix_to_filter=None):
        """
        注意！对于类似以下格式的内容，需要把"好的"留下！
        ```
        cache = deque(
            [
                {"event": "think", "content": "<th", "cover": False},
                {"event": "think", "content": "in", "cover": False},
                {"event": "think", "content": "k>", "cover": False},
                {"event": "think", "content": "\n好的", "cover": False},
            ]
        )
        ```
        """
        cache = self.cache
        # 针对 think event 的过滤
        think_event_filter_symbols = deepcopy(self.think_symbols)
        if final_answer_prefix_to_filter:
            think_event_filter_symbols.append(final_answer_prefix_to_filter)
        hit_think, recall_event_think = self.common_filter(cache, think_event_filter_symbols, StreamEventType.THINK)

        # 针对 final answer JSON BLOB 后缀的过滤
        if final_answer_suffix_to_filter:
            hit_suffix, recall_event_suffix = self.common_filter(
                cache, [final_answer_suffix_to_filter], StreamEventType.TEXT
            )
        else:
            hit_suffix = False
            recall_event_suffix = None

        if hit_think or hit_suffix:
            init_events = list(deepcopy(cache))
            if hit_think:
                # 去除 think 的 event，因为已经合并和过滤了
                # 需保证 think 在 text 前面
                remain_events = []
                have_appended_recall_event_think = False
                for event in init_events:
                    if event.get("event") == StreamEventType.THINK:
                        if recall_event_think and not have_appended_recall_event_think:
                            remain_events.append(recall_event_think)
                            have_appended_recall_event_think = True
                    else:
                        remain_events.append(event)
            else:
                remain_events = init_events

            if hit_suffix:
                # 去除 text 的 event，因为已经合并和过滤了
                # 需保证 think 在 text 前面
                # 因为认为 cache 中原始的 think 一定在 text 前面，所以这样处理即可：
                remain_events = [event for event in remain_events if event.get("event") != StreamEventType.TEXT]
                if recall_event_suffix:
                    remain_events.append(recall_event_suffix)

            cache = deque(remain_events)
        self.cache = cache

    def check_and_append(self, cache, ret: BkAiStreamEvent):
        """在刚从 think 切换到 text 逻辑之前需要进行的特殊处理"""
        # 前端渲染要求在 think 和 text 之间必须保证有 "\n\n" 的 text 内容
        if (
            cache
            and (cache[-1].get("event") in (StreamEventType.THINK, StreamEventType.REFERENCE_DOC))
            and (ret.get("event") == StreamEventType.TEXT)
            and (not ret.get("content").startswith("\n"))
        ):
            if ret.get("content"):
                ret["content"] = "\n\n" + ret["content"]
            else:
                ret["content"] = "\n\n"
        cache.append(ret)

    def _yield_ret(self, ret: BkAiStreamEvent | None = None, done=False):
        if done:
            return "data: [DONE]\n\n"
        ret = deepcopy(ret)
        event = ret.pop("event", StreamEventType.ERROR)
        ret = {"event": event.value, **ret}
        return f"data: {json.dumps(ret)}\n\n"

    def stream_standard_event(self, g: Iterator[StreamEvent]) -> Generator[str, None]:
        self.agent_think_start_time = time.time()
        try:
            # 处理 LangGraph astream_events
            for item in g:
                for event in self.process_event(item):
                    yield self._yield_ret(event)

            # 处理 StructuredChatCommonQAAgent 的结束逻辑
            if self.agent_type == BKAiStreamingAgentType.StructuredChatCommonQAAgent:
                # 处理剩余的缓存事件
                for event in self.handle_structured_chat_end():
                    yield self._yield_ret(event)

            # 发送完成事件
            done_event = BkAiStreamEvent(event=StreamEventType.DONE, content=self.final_result, cover=False)
            yield self._yield_ret(done_event)
        except Exception as e:
            logger.exception(f"流处理过程中发生错误: {e}")
            error_event = BkAiStreamEvent(
                event=StreamEventType.ERROR,
                code=e.code if hasattr(e, "code") else 400,
                message=e.response_data() if hasattr(e, "response_data") else traceback.format_exc(),
            )
            yield self._yield_ret(error_event)

        finally:
            yield self._yield_ret(done=True)

    def process_event(self, item: Dict[str, Any]) -> Generator[BkAiStreamEvent]:
        """处理 Runnable 事件

        Args:
            item: Runnable 事件项

        Returns:
            转换后的前端事件，如果不需要输出则返回 None
        """
        # 处理空事件
        if item == Empty:
            if self.last_ret_is_empty or self.first_chunk:
                event = BkAiStreamEvent(
                    event=StreamEventType.TEXT, content=self.LOADING_AGENT_MESSAGE, cover=self.last_ret_is_empty
                )
                yield from self.handle_ret_event(event, None)
        # 处理聊天模型流事件
        elif item.get("event") == "on_chat_model_stream" and self.front_end_display:
            chunk = item.get("data", {}).get("chunk")
            run_id = item.get("run_id")
            self.run_info[run_id]["tool_call"] = bool(chunk.tool_call_chunks)
            if not self.skip_thought and (
                chunk.content
                or chunk.additional_kwargs.get("reasoning_content", None)
                or self.run_info[run_id].get("tool_call")
            ):
                yield from self.handle_on_chat_model_stream(chunk)
        # 处理自定义事件
        elif item.get("event") == "on_custom_event":
            yield from self.handle_on_custom_event(item)
        # 处理工具结束事件
        elif item.get("event") == "on_tool_end":
            data = item.get("data", {})
            for event in self.handle_on_tool_end(data):
                yield event

    def handle_ret(self, ret: BkAiStreamEvent | None) -> Generator[BkAiStreamEvent]:
        if not ret:
            return
        recall_ret = None
        if self.agent_type == BKAiStreamingAgentType.StructuredChatCommonQAAgent:
            recall_ret = self.handle_structured_chat_common_qa(ret)
        yield from self.handle_ret_event(ret, recall_ret)

    def handle_structured_chat_common_qa(self, ret: BkAiStreamEvent):
        recall_ret = None
        if "content" in ret:
            ret["event"] = self.cur_event_type
        # 一旦出现 Final Answer 模式，之后的所有过程都视为 agent 的正式回答过程
        # NOTE: 需要在 non_think_content 中匹配到的 Final Answer 才能触发结束，think 过程中匹配到的不算
        if not self.final_answer_occurred:
            for final_answer_prefix, final_answer_suffix in zip(self.final_answer_prefixes, self.final_answer_suffixes):
                if final_answer_prefix in self.non_think_content:
                    self.final_answer_occurred = True
                    self.final_answer_prefix_to_filter = final_answer_prefix
                    # 注：后续放到 cache 前的 ret 内容从出现 final answer 的下一次开始进行了针对 \n 的转义操作
                    # 为了不影响命中，此处也同步进行相同的转义操作
                    self.final_answer_suffix = final_answer_suffix
                    self.final_answer_suffix_to_filter = final_answer_suffix.replace("\\n", "\n")
                    # 需要加上特殊的 end_content 才能作为最终的 final_answer_suffix
                    self.final_answer_suffix_to_filter += deepcopy(self.end_content)
                    if not self.final_result.endswith(final_answer_prefix):
                        # 这种情况下说明最终答案有一小块跟在了 final_answer_prefix 最后一个块的后面
                        # 需要将这块内容补回来，并将 think 末尾的那段内容截掉
                        # NOTE: 使用 rfind 寻找最后匹配的那个final answer，确保匹配到的是
                        # non_think_content 中的 final answer 块
                        start_index = self.final_result.rfind(final_answer_prefix)
                        if start_index == -1:
                            raise RuntimeError(
                                f"结果子串提取有误。\nfinal_result: {self.final_result}\n"
                                f"final_answer_prefix: {final_answer_prefix}\n"
                            )
                        end_index = start_index + len(final_answer_prefix)
                        recall_ret_prefix_content = self.final_result[end_index:]
                        try:
                            ret["content"] = ret["content"][: -len(recall_ret_prefix_content)]
                        except Exception:
                            raise RuntimeError(
                                f"子串去除有误。\nret: {ret}\nrecall_ret_prefix_content: {recall_ret_prefix_content}\n"
                            )
                        # 处理 json 格式内的 final answer 的内容（包含被转义的情况）以供 markdown 渲染。
                        # TODO: 同步更新 final_result
                        # NOTE: 需要在上述 ret["content"][: -len(recall_ret_prefix_content)] 之后
                        # 执行这个动作！否则会把 ret["content"] 多去了一个字符
                        recall_ret_prefix_content = recall_ret_prefix_content.replace("\\n", "\n")
                        recall_ret = BkAiStreamEvent(
                            event=StreamEventType.TEXT,
                            content=recall_ret_prefix_content,
                            cover=bool(self.last_ret_is_empty),
                        )
                    self.cur_event_type = StreamEventType.TEXT
                    ret["elapsed_time"] = (time.time() - self.agent_think_start_time) * 1000
                    break
        if self.final_answer_occurred and not self.first_time_final_answer:  # noqa: SIM102
            # NOTE: final_answer_suffix 有可能不在同一个 ret 的 content 中，
            # 所以 final_answer_suffix 不能在此处原地剔除，
            # 需要在 cache 中合并判断和剔除。例子如下所示：
            # =====> {'event': 'text', 'content': '）。', 'cover': False}
            # =====> {'event': 'text', 'content': '"\n', 'cover': False}
            # =====> {'event': 'text', 'content': '}\n', 'cover': False}
            # =====> {'event': 'text', 'content': '```', 'cover': False}
            # NOTE: 如果 first_time_final_answer 为 True，则是刚从 think 变成 text 的时候，
            # 当前的 ret 就还不属于 final answer 类型，因此不能进入本分支

            # 以下内容用于处理 json 格式内的 final answer 的内容（包含被转义的情况）以供 markdown 渲染。
            # TODO: 同步更新 final_result
            # 目前仅支持处理换行符：\\n --> \n
            if "content" in ret:
                ret["content"] = ret["content"].replace("\\n", "\n")
                if self.cache and self.cache[-1].get("content", "").endswith("\\") and ret["content"].startswith("n"):
                    # 处理这样的case：
                    # data: {"event": "text", "content": "如下", "cover": false}
                    # data: {"event": "text", "content": "：", "cover": false}
                    # data: {"event": "text", "content": "\\", "cover": false}
                    # data: {"event": "text", "content": "n1", "cover": false}
                    # data: {"event": "text", "content": ".", "cover": false}
                    # data: {"event": "text", "content": " 下", "cover": false}
                    # data: {"event": "text", "content": "载", "cover": false}
                    self.cache[-1]["content"] = self.cache[-1]["content"][:-1]
                    ret["content"] = "\n" + ret["content"][1:]
        # 更新标识变量
        if self.final_answer_occurred:
            self.first_time_final_answer = False
        return recall_ret

    def handle_ret_event(
        self, ret: BkAiStreamEvent, recall_ret: Optional[BkAiStreamEvent]
    ) -> Generator[BkAiStreamEvent]:
        """处理 ret 逻辑，与原始 CommonQAStreamingMixIn 的 if ret 部分保持一致"""
        self.first_chunk = False
        self.last_ret_is_empty = ret.get("content", "") == self.LOADING_AGENT_MESSAGE

        if self.agent_type == BKAiStreamingAgentType.StructuredChatCommonQAAgent:
            # StructuredChatCommonQAAgent 的复杂处理逻辑
            if ret.get("content", "") == self.LOADING_AGENT_MESSAGE:
                self.last_event_type = ret["event"]
                yield ret
            else:
                # NOTE: 首次出现 ``` 时，需要在前面添加一个换行符，防止前端没有渲染出来
                if "``" in ret.get("content", "") and self.first_triple_backticks:
                    ret["content"] = "\n" + ret["content"]
                    self.first_triple_backticks = False
                # NOTE: 只有非 self.LOADING_AGENT_MESSAGE 的 event 可以放到 cache 中
                self.check_and_append(self.cache, ret)
                if recall_ret:
                    # 如果 cache 非空，先 pop 最开始的元素，再将补充的 recall_ret 给添加进来
                    if self.cache:
                        ret = self.cache.popleft()
                        self.last_event_type = ret["event"]
                        yield ret
                    self.check_and_append(self.cache, ret)

                self.cache_filter(self.final_answer_prefix_to_filter, self.final_answer_suffix_to_filter)

                # 防止出现think为空或第一个 think event 的 cover 为 False 的情况
                if (
                    self.final_answer_occurred
                    and self.cache[-1]["event"] == StreamEventType.THINK
                    and self.first_think_event
                ):
                    # 如果所有think event加起来过滤后为空，则删除，防止输出空的思考过程
                    if self.cache[-1]["content"].strip() == "":
                        self.cache.pop()
                        # 如果过滤后 cache 为空，要将 last_ret_is_empty 设置为 True，确保第一个 text 的 cover 是 True
                        if len(self.cache) == 0:
                            self.last_ret_is_empty = True
                    # 如果过滤后只剩一个think event且是第一个，要将 cover 设置为 True
                    elif len(self.cache) == 1:
                        self.cache[0]["cover"] = True
                        self.first_think_event = False

                if len(self.cache) == self.max_cache_length:
                    ret = self.cache.popleft()
                    self.last_event_type = ret["event"]
                    if self.last_event_type == StreamEventType.THINK:
                        self.first_think_event = False
                    yield ret
        else:
            yield ret

    def handle_structured_chat_end(self) -> Generator[BkAiStreamEvent]:
        """处理 StructuredChatCommonQAAgent 的结束逻辑"""
        # 以下逻辑用于利用 self.end_content 标志跟 final_answer_suffix_to_filter 拼接后进行尾部去除
        if len(self.cache) == self.max_cache_length:
            ret = self.cache.popleft()
            self.last_event_type = ret["event"]
            yield ret
        # 如果 cache 最后一个元素包含 `\n，需要在 final_answer_suffix_to_filter 后面也添加一个换行符才能把后缀过滤掉
        if self.cache and "`\n" in self.cache[-1].get("content", ""):
            self.final_answer_suffix_to_filter = (
                self.final_answer_suffix.replace("\\n", "\n") + "\n" + deepcopy(self.end_content)
            )

        end_event = BkAiStreamEvent(
            event=StreamEventType.TEXT,
            content=deepcopy(self.end_content),
            cover=False,
        )
        self.check_and_append(self.cache, end_event)
        len_before_filtering = len(self.cache)
        first_true = bool(self.cache) and self.cache[0].get("cover", False)
        self.cache_filter(self.final_answer_prefix_to_filter, self.final_answer_suffix_to_filter)

        # 如果cache过滤前第一个元素的 cover 是 True，则过滤后 cover 应该是 True
        if first_true:
            self.cache[0]["cover"] = True

        if len(self.cache) == len_before_filtering:
            # 如果没 filter 到，则还是将 end_ret 剔除
            self.cache.pop()

        while self.cache:
            ret = self.cache.popleft()
            self.last_event_type = ret["event"]
            yield ret

        # 过滤 think 符号
        for think_symbol in self.think_symbols:
            self.final_result = self.final_result.replace(think_symbol, "")

        # 如果 done 之前的最后一个 event 是 think 类型，则说明从 think 内容中解析结论失败，需额外发送一条 text event
        # 防止报错：
        # {\"result\":false,\"data\":null,\"code\":\"1500400\",\"message\":\"content: 该字段不能为空。\"}" }
        if self.last_event_type == StreamEventType.THINK:
            # 先发一个确保带 elapsed_time 的 think event
            think_event = BkAiStreamEvent(
                event=StreamEventType.THINK,
                content="\n",
                cover=False,
                elapsed_time=(time.time() - self.agent_think_start_time) * 1000,
            )
            yield think_event

            # 再发一个确保为 text 的 event
            logger.warning(
                "Fail to derive the final answer from the thinking process. "
                f"The final result is: \n{self.final_result}\n"
            )
            cover = bool(self.last_ret_is_empty)
            text_event = BkAiStreamEvent(
                event=StreamEventType.TEXT,
                content="抱歉，由于LLM指令遵从效果欠佳，尝试从思考内容中解析最终结论失败，请从思考内容中获取结论。",
                cover=cover,
            )
            yield text_event

    def handle_on_chat_model_stream(self, chunk: BaseMessageChunk) -> Generator[BkAiStreamEvent]:
        """处理聊天模型流事件"""
        cover = bool(self.last_ret_is_empty)
        reasoning_content = chunk.additional_kwargs.get("reasoning_content", None)
        is_tool_call = bool(chunk.tool_call_chunks)
        # 根据智能体类型和内容类型分发处理
        ret = None
        if self.agent_type == BKAiStreamingAgentType.StructuredChatCommonQAAgent:
            # 如果是 StructuredChatCommonQAAgent，则会将所有中间 action 步骤也归为 think
            # 判断最终答案的逻辑在后面，所以这里先统一成 text
            if reasoning_content:
                content = reasoning_content
            else:
                content = chunk.content
                self.non_think_content += content
            self.final_result += content
            ret = BkAiStreamEvent(
                event=StreamEventType.TEXT,
                content=content,
                cover=cover,
            )
        elif self.agent_type == BKAiStreamingAgentType.ToolCallingCommonQAAgent:
            if reasoning_content:
                self.has_reasoning_content = True
                self.final_result += reasoning_content
                ret = BkAiStreamEvent(event=StreamEventType.THINK, content=reasoning_content, cover=cover)
            elif is_tool_call:
                if name := chunk.tool_call_chunks[0].get("name"):
                    self.tool_calling = True
                    # 如果不是第一次调用工具，需要补上一个```,
                    # 在LangGraph 适配过程中存在问题，展示移除了 需要补上一个``` 的逻辑
                    # log_prefix = "\n```\n" if self.has_tool_call else ""
                    log_prefix = "\n\n" if self.has_tool_call else ""
                    # 如果不是第一次调用工具，将first_tool_args还原为True
                    if self.has_tool_call:
                        self.first_tool_args = True
                    ret = BkAiStreamEvent(
                        event=StreamEventType.THINK,
                        content=f'{log_prefix}\n```json\n"action": "{name}",\n',
                        cover=cover,
                    )
                elif chunk.tool_call_chunks[0].get("args"):
                    # 如果是第一个tool args，需要在前面加上'"action_input":'
                    if self.first_tool_args:
                        ret = BkAiStreamEvent(
                            event=StreamEventType.THINK,
                            content='"action_input":',
                            cover=cover,
                        )
                        yield ret
                        self.final_result += ret["content"]
                        self.first_tool_args = False

                    ret = BkAiStreamEvent(
                        event=StreamEventType.THINK,
                        content=chunk.tool_call_chunks[0].get("args"),
                        cover=cover,
                    )
                else:
                    return
                self.final_result += ret["content"]
                self.has_tool_call = True
            elif self.force_think_content:
                # LangGraph 适配专用，对于非总结节点，强制输出为 think 标签
                ret = BkAiStreamEvent(
                    event=StreamEventType.THINK,
                    content=chunk.content,
                    cover=cover,
                )
                self.has_reasoning_content = True
                self.final_result += ret["content"]
            else:
                # 如果首次从 think 切到 text 内容，需要先补发一条带 elapsed_time的 think event 以供识别
                if (
                    self.has_reasoning_content or self.has_tool_call or self.has_custom_event
                ) and chunk.content.strip():
                    self.has_reasoning_content = False
                    self.has_tool_call = False
                    self.has_custom_event = False
                    ret = BkAiStreamEvent(
                        event=StreamEventType.THINK,
                        content="\n",
                        cover=False,
                        elapsed_time=(time.time() - self.agent_think_start_time) * 1000,
                    )
                    if not self.tool_calling:
                        yield from self.handle_ret(ret)
                    self.final_result += ret["content"]
                ret = BkAiStreamEvent(
                    event=StreamEventType.TEXT,
                    content=chunk.content,
                    cover=cover,
                )
                self.final_result += ret["content"]
                self.non_think_content += ret["content"]
        yield from self.handle_ret(ret)

    def handle_on_custom_event(self, item: Dict[str, Any]) -> Generator[BkAiStreamEvent]:
        """处理自定义事件"""
        cover = bool(self.last_ret_is_empty)
        custom_data = item.get("data", {})
        ret = None
        # on_tool_node_finish 可能直接携带 ToolMessage
        if isinstance(custom_data, ToolMessage) and self.front_end_display:
            yield from self.handle_on_tool_end({"output": custom_data.content})
            return
        if not isinstance(custom_data, dict):
            return
        data = custom_data
        # 处理前端显示标识
        if "front_end_display" in data:
            self.front_end_display = data["front_end_display"]
        # 处理自定义返回内容
        elif "custom_return_chunk" in data and self.front_end_display:
            content = data["custom_return_chunk"]
            self.final_result += content
            ret = BkAiStreamEvent(event=StreamEventType.TEXT, content=content, cover=cover)
        # 处理参考文档
        elif item.get("name", "") == CustomMessageType.KNOWLEDGE_RAG_RESULT.value and self.front_end_display:
            documents = []
            reference_docs = data.get("data", [])
            for _each in reference_docs:
                if not isinstance(_each, dict):
                    continue
                preview_path = _each.get("originFile", "")
                file_path = parse_qs(urlparse(preview_path).query).get("anchorPath", [""])[0].split("/", 2)[-1]
                documents.append(
                    {
                        "metadata": {
                            "path": _each.get("url", ""),
                            "file_path": file_path,
                            "display_name": _each.get("name", ""),
                            "preview_path": _each.get("originFile", ""),
                        }
                    }
                )
            ret = BkAiStreamEvent(event=StreamEventType.REFERENCE_DOC, documents=documents, cover=True)
        # 处理压缩日志
        elif "compress_log" in data and self.front_end_display:
            ret = BkAiStreamEvent(event=StreamEventType.THINK, content=data["compress_log"], cover=cover)
        # 处理自定义智能体完成
        elif "custom_agent_finish" in data and self.front_end_display:
            content = data["custom_agent_finish"]
            self.final_result += content
            ret = BkAiStreamEvent(event=StreamEventType.TEXT, content=content, cover=cover)
        # 处理意图识别结果
        elif "intent_recognition_result" in data and self.front_end_display:
            self.has_custom_event = True
            ret = BkAiStreamEvent(event=StreamEventType.THINK, content=data["intent_recognition_result"], cover=cover)
        elif "force_think_content" in data and self.front_end_display:
            self.force_think_content = data["force_think_content"]

        yield from self.handle_ret(ret)

    def handle_on_tool_end(self, data) -> Generator[BkAiStreamEvent]:
        self.tool_calling = False
        # TODO: 可能需要考虑异步是否会导致event的乱序问题
        # 打印工具输出
        tool_output_content = str(data.get("output", ""))
        # 报错信息封装（与原始逻辑完全一致）
        if " is not a valid tool, try one of " in tool_output_content:
            err_tool = tool_output_content.split(" is not a valid tool, try one of ")[0]
            tool_output_content = f"LLM 选择的工具“{err_tool}”超出了给定工具的范围，本次工具调用失败。"
        elif tool_output_content == ACTION_INPUT_ERR_MSG:
            tool_output_content = "LLM 生成的工具调用参数不正确，本次工具调用失败。"
        elif tool_output_content == OUTPUT_PARSER_ERR_MSG:
            tool_output_content = OUTPUT_PARSER_ERR_MSG

        if len(tool_output_content) > self.max_tool_output_len:
            tool_output_content = tool_output_content[: self.max_tool_output_len] + "（内容过长，已截断）"

        # NOTE: 重要操作！
        # 由于 LLM 输出结果不可控，为了防止 stream 过程中输出的 JSON BLOB 中有开始的 ``` 而没有结束的 ```
        # 这里在返回工具调用结果之前，前判断当前 final_result 中 ``` 已经出现的次数
        # 如果是奇数次，则手工拼接一个 ``` 防止前端渲染的时候乱了
        log_prefix = "\n```\n" if self.final_result.count("```") % 2 == 1 else ""

        content = f"{log_prefix}\n\n以下是该 Agent Action 的结果：\n```text\n{tool_output_content}\n```\n\n"

        self.first_tool_args = True
        self.final_result += content
        cover = bool(self.last_ret_is_empty)
        ret = BkAiStreamEvent(event=StreamEventType.THINK, content=content, cover=cover)
        yield from self.handle_ret(ret)


class AgentStreamAdapter:
    def __init__(self, agent_type: str | None = None):
        self.agent_type: BKAiStreamingAgentType = (
            BKAiStreamingAgentType.StructuredChatCommonQAAgent
            if agent_type and "deepseek" in agent_type
            else BKAiStreamingAgentType.ToolCallingCommonQAAgent
        )

    # 流协议处理
    def stream_standard_event(
        self,
        agent_e,
        cfg,
        input_state,
        skip_thought=False,
        timeout: int = 30,
        async_finalizer=None,
    ):
        try:
            protocol = BkAiStreamingProtocol(
                skip_thought=skip_thought,
                timeout=timeout,
                max_tool_output_len=settings.MAX_TOOL_OUTPUT_LEN,
                max_cache_length=settings.MAX_CACHE_LENGTH,
                agent_type=self.agent_type,
            )
            _aiter = agent_e.astream_events(
                input_state,
                config=cfg,
                version="v2",
                timeout=timeout,
                durability="exit",
            )
            _aiter = async_generator_with_timeout(_aiter, timeout=timeout)
            g = async_to_sync_generator(_aiter, async_finalizer=async_finalizer)
            yield from protocol.stream_standard_event(g)
        except Exception:
            logger.error(traceback.format_exc())
