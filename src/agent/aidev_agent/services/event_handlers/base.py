# -*- coding: utf-8 -*-
"""AG-UI 事件处理器抽象基类

定义会话回写的通用逻辑，支持三种使用方式：
1. 简单场景：只实现 _do_create_content()，使用默认事件处理逻辑
2. 扩展场景：覆盖 handle_model_end/handle_tool_finish 等方法自定义处理
3. 完全自定义：覆盖 __call__ 方法处理原始事件

断点续传机制：
- 不使用占位消息，而是通过会话状态（session.status）判断
- 流式开始时：set_streaming_started() 将会话状态设为 running
- 流式结束时：set_streaming_finished() 将会话状态设为 finished
- 前端查询消息列表时，后端根据 session.status == running 动态标记最后一条 AI 消息为 streaming
"""

import json
import uuid
from abc import ABC, abstractmethod
from logging import getLogger
from typing import Any, Callable

from ag_ui.core import BaseEvent, EventType, RunErrorEvent
from ag_ui.core.events import RawEvent, TextMessageContentEvent, TextMessageEndEvent, TextMessageStartEvent

from aidev_agent.core.ag_ui.types import (
    CustomEventNames,
    CustomMessageType,
    ExtendFunctionCall,
    ExtendToolCall,
    LangGraphEventTypes,
)
from aidev_agent.core.ag_ui.utils import camel_to_snake
from aidev_agent.enums import PromptRole

logger = getLogger(__name__)


def dict_keys_camel_to_snake(d: dict) -> dict:
    """将字典的 key 从 camelCase 转换为 snake_case"""
    return {camel_to_snake(k): v for k, v in d.items()}


class BaseSessionWriter(ABC):
    """会话回写器抽象基类

    通过 __call__ 方法接收所有 AG-UI 事件，分发到对应的类型化处理方法。

    断点续传通过会话状态判断实现（不使用占位消息）：
    - 流式开始：set_streaming_started() 更新 session.status = running
    - 流式结束：set_streaming_finished() 更新 session.status = finished
    - 消息直接通过 create 创建，无需占位/变形

    使用方式：
    1. 简单场景：只实现 `_do_create_content` 方法，使用默认事件处理逻辑
    2. 扩展场景：覆盖 `handle_model_end`/`handle_tool_finish` 等方法自定义处理
    3. 完全自定义：覆盖 `__call__` 方法处理原始事件

    Example:
        ```python
        # 简单场景 - 只需实现回写方法
        class MyWriter(BaseSessionWriter):
            def _do_create_content(self, payload, headers):
                db.save(payload)

        # 扩展场景 - 自定义某类事件的处理
        class MyWriter(BaseSessionWriter):
            def handle_reference_document(self, event):
                # 自定义引用文档的处理逻辑
                ...

        # 完全自定义 - 直接处理原始事件
        class MyWriter(BaseSessionWriter):
            def __call__(self, event):
                # 完全自定义的事件处理逻辑
                ...
        ```
    """

    def __init__(self, session_code: str, username: str = "", tools: list | None = None):
        """初始化回写器

        Args:
            session_code: 会话标识
            username: 用户名
            tools: 工具列表，用于获取工具描述信息
        """
        self.session_code: str = session_code
        self.username: str = username
        self._tools_mapping: dict[str, Any] = {tool.name: tool for tool in tools} if tools else {}
        # 用于内存去重，避免重复回写
        self._written_message_ids: set[str] = set()
        # 用于追踪正在流式输出的消息，累积内容
        # key: message_id, value: {"content": str}
        self._streaming_messages: dict[str, dict] = {}

    # ---------- 公共事件入口 ----------

    def __call__(self, event: BaseEvent) -> None:
        """事件入口 - 分发到对应的处理方法

        Args:
            event: AG-UI 事件
        """
        if event.type == EventType.RAW:
            self._dispatch_raw_event(event)
        elif event.type == EventType.RUN_ERROR:
            self.handle_run_error(event)
        elif event.type == EventType.TEXT_MESSAGE_START:
            self.handle_text_message_start(event)
        elif event.type == EventType.TEXT_MESSAGE_CONTENT:
            self.handle_text_message_content(event)
        elif event.type == EventType.TEXT_MESSAGE_END:
            self.handle_text_message_end(event)

    def _dispatch_raw_event(self, event: RawEvent) -> None:
        """分发原始事件到类型化处理方法"""
        langchain_event = event.event.get("event")

        if langchain_event == LangGraphEventTypes.OnChatModelEnd.value:
            self.handle_model_end(event)
        elif langchain_event == LangGraphEventTypes.OnCustomEvent.value:
            self._dispatch_custom_event(event)

    def _dispatch_custom_event(self, event: RawEvent) -> None:
        """分发自定义事件"""
        event_name = event.event.get("name", "")

        if event_name == CustomEventNames.OnToolNodeFinish.value:
            self.handle_tool_finish(event)
        elif event_name == CustomMessageType.KNOWLEDGE_RAG_RESULT.value:
            self.handle_reference_document(event)

    # ---------- 事件处理方法 ----------

    def handle_text_message_start(self, event: TextMessageStartEvent) -> None:
        """处理文本消息开始事件，开始追踪流式内容

        Args:
            event: TEXT_MESSAGE_START 事件
        """
        message_id = event.message_id
        if not message_id or message_id in self._written_message_ids:
            return

        # 初始化消息内容追踪
        self._streaming_messages[message_id] = {"content": ""}

    def handle_text_message_content(self, event: TextMessageContentEvent) -> None:
        """处理文本消息内容事件，累积内容

        Args:
            event: TEXT_MESSAGE_CONTENT 事件
        """
        message_id = event.message_id
        if not message_id:
            return

        # 累积内容
        if message_id in self._streaming_messages:
            self._streaming_messages[message_id]["content"] += event.delta or ""

    def handle_text_message_end(self, event: TextMessageEndEvent) -> None:
        """处理文本消息结束事件

        注意：实际的消息回写由 handle_model_end 完成，
        这里只负责记录消息结束状态，避免重复处理。

        Args:
            event: TEXT_MESSAGE_END 事件
        """
        message_id = event.message_id
        if not message_id:
            return

    def handle_model_end(self, event: RawEvent) -> None:
        """处理模型输出结束事件，回写 assistant 消息

        Args:
            event: 包含 on_chat_model_end 数据的原始事件
        """
        output_message = event.event.get("data", {}).get("output")
        if not output_message:
            return

        message_id = output_message.id
        if message_id in self._written_message_ids:
            return

        # 构建 tool_calls
        tool_calls = self._build_tool_calls(output_message)

        # 处理 reasoning 内容（如 deepseek-reasoner）
        reasoning_content = output_message.additional_kwargs.get("reasoning_content")

        # 处理最终回复内容
        content = self._resolve_content(output_message.content, tool_calls, reasoning_content)

        if reasoning_content:
            self._write_reasoning_message(
                message_id=message_id,
                reasoning_content=reasoning_content,
                output_message=output_message,
            )

        self._write_assistant_message(
            message_id=message_id,
            content=content,
            tool_calls=tool_calls,
        )

        self._written_message_ids.add(message_id)
        # 清理追踪
        self._streaming_messages.pop(message_id, None)

    def handle_tool_finish(self, event: RawEvent) -> None:
        """处理工具执行完成事件，回写 tool 消息

        Args:
            event: 包含 on_tool_node_finish 数据的原始事件
        """
        output_message = event.event.get("data")
        if not output_message:
            return

        tool_call_id = output_message.tool_call_id
        if tool_call_id in self._written_message_ids:
            return

        # 映射状态：success -> success, error -> fail
        platform_status = "fail" if output_message.status == "error" else "success"

        self._create_session_content(
            message_id=output_message.id or tool_call_id,
            role=PromptRole.TOOL.value,
            content=output_message.content,
            status=platform_status,
            builtin_property={
                "message_id": tool_call_id,
                "tool_call_id": tool_call_id,
                "additional_kwargs": output_message.additional_kwargs,
            },
        )
        self._written_message_ids.add(tool_call_id)

    def handle_run_error(self, event: RunErrorEvent) -> None:
        """处理运行时错误事件，回写 assistant 失败消息

        Args:
            event: 运行错误事件
        """
        error_message_id = f"error_{uuid.uuid4().hex[:12]}"

        self._create_session_content(
            message_id=error_message_id,
            role=PromptRole.ASSISTANT.value,
            content=event.message,
            status="fail",
            builtin_property={
                "message_id": error_message_id,
                "error": True,
            },
        )

    def handle_reference_document(self, event: RawEvent) -> None:
        """处理引用文档事件，回写 activity 消息

        Args:
            event: 包含 reference_document 数据的原始事件
        """
        event_data = event.event.get("data", {})
        message_id = event_data.get("message_id")
        reference_documents = [dict_keys_camel_to_snake(each) for each in event_data.get("data", [])]

        if not message_id:
            message_id = f"ref_{uuid.uuid4().hex[:12]}"

        if message_id in self._written_message_ids:
            return

        # content 需要序列化为 JSON 字符串，因为数据库 content 字段是 TextField
        self._create_session_content(
            message_id=message_id,
            role=PromptRole.ACTIVITY.value,
            content=json.dumps(reference_documents, ensure_ascii=False),
            status="success",
            builtin_property={
                "message_id": message_id,
                "type": "reference_document",
            },
        )
        self._written_message_ids.add(message_id)

    # ---------- handle_model_end 辅助方法 ----------

    def _build_tool_calls(self, output_message: Any) -> list:
        """从模型输出中构建 tool_calls 列表"""
        tool_calls = []
        for each in output_message.tool_calls or []:
            _tool = self._tools_mapping.get(each["name"])
            tool_calls.append(
                ExtendToolCall(
                    id=each["id"],
                    function=ExtendFunctionCall(
                        name=each["name"],
                        arguments=json.dumps(each["args"]),
                        description=_tool.description if _tool else "",
                        mcp_name=_tool.metadata.get("mcp_name", "") if _tool and _tool.metadata else "",
                    ),
                ).model_dump()
            )
        return tool_calls

    def _resolve_content(self, content: str, tool_calls: list, reasoning_content: str | None) -> str:
        """解析最终回复内容

        对于 DeepSeek reasoning 模型，最终回复可能在 reasoning_content 而不是 content。
        当有 tool_calls 时，content 为空是正常的（AI 只是调用工具）。
        当没有 tool_calls 且 content 为空时，尝试使用 reasoning_content 作为回复内容。
        """
        content_stripped = content.strip() if content else ""

        if not content_stripped and not tool_calls and reasoning_content:
            # reasoning 模型的最终回复在 reasoning_content 中
            return reasoning_content
        elif not content_stripped and tool_calls:
            # 有 tool_calls 但 content 为空/只有空白字符，使用一个有意义的占位符
            return "正在调用工具..."
        elif not content_stripped:
            # 没有 tool_calls 也没有内容，使用空字符串（可能会失败）
            return ""
        return reasoning_content

    def _write_reasoning_message(
        self,
        message_id: str,
        reasoning_content: str,
        output_message: Any,
    ) -> None:
        """回写 reasoning 消息

        Args:
            message_id: 当前 assistant 消息 ID
            reasoning_content: reasoning 内容
            output_message: 模型输出对象
        """
        reasoning_message_id = f"rsn_{message_id}"
        if reasoning_message_id in self._written_message_ids:
            return

        reasoning_content_list = reasoning_content if isinstance(reasoning_content, list) else [reasoning_content]
        reasoning_json = json.dumps(reasoning_content_list, ensure_ascii=False)
        reasoning_property = {
            "message_id": reasoning_message_id,
            "duration": output_message.additional_kwargs.get("reasoning_time", 0),
        }

        self._create_session_content(
            message_id=reasoning_message_id,
            role=PromptRole.REASONING.value,
            content=reasoning_json,
            status="success",
            builtin_property=reasoning_property,
        )

        self._written_message_ids.add(reasoning_message_id)

    def _write_assistant_message(
        self,
        message_id: str,
        content: str,
        tool_calls: list,
    ) -> None:
        """回写 assistant 消息

        Args:
            message_id: assistant 消息 ID
            content: 消息内容
            tool_calls: 工具调用列表
        """
        assistant_property = {
            "message_id": message_id,
            "tool_calls": tool_calls,
        }

        self._create_session_content(
            message_id=message_id,
            role=PromptRole.ASSISTANT.value,
            content=content,
            status="success",
            builtin_property=assistant_property,
        )

    # ---------- 底层回写方法 ----------

    def _get_headers(self) -> dict[str, str]:
        """构建请求头"""
        return {"X-BKAIDEV-USER": self.username} if self.username else {}

    def _safe_call(self, fn: Callable, message_id: str, action: str, **kwargs: Any) -> None:
        """安全调用回写函数，统一处理异常和日志

        Args:
            fn: 实际执行的回写函数（_do_create_content 等）
            message_id: 消息 ID，仅用于日志
            action: 操作名称，仅用于日志（如 "create"）
            **kwargs: 传递给 fn 的参数
        """
        try:
            fn(**kwargs)
        except Exception as e:
            logger.error(f"Failed to {action} session content: message_id={message_id}, error={e}", exc_info=True)

    def _create_session_content(
        self,
        message_id: str,
        role: str,
        content: str | list,
        status: str,
        builtin_property: dict[str, Any],
    ) -> None:
        """创建会话内容（内部方法）"""
        payload = {
            "session_code": self.session_code,
            "role": role,
            "content": content,
            "status": status,
            "property": {
                "builtin_property": builtin_property,
            },
        }
        self._safe_call(self._do_create_content, message_id, "create", payload=payload, headers=self._get_headers())

    @abstractmethod
    def _do_create_content(self, payload: dict[str, Any], headers: dict[str, str]) -> None:
        """执行具体的回写操作

        子类必须实现此方法来定义具体的回写逻辑。

        Args:
            payload: 回写数据，包含 session_code, role, content, status, property 等字段
            headers: HTTP 头信息，包含用户信息等

        Raises:
            Exception: 回写失败时抛出异常，由基类统一处理日志记录
        """

    # ---------- 断点续传支持（基于会话状态判断） ----------

    def set_streaming_started(self) -> None:
        """标记流式传输开始

        子类应覆盖此方法来更新会话状态为 running。
        默认实现为空操作。
        """

    def set_streaming_finished(self) -> None:
        """标记流式传输结束

        子类应覆盖此方法来更新会话状态为 finished。
        默认实现为空操作。
        """
