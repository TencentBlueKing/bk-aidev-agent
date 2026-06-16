# -*- coding: utf-8 -*-
"""
SSE 流消费层。
负责将 Agent 产出的 SSE 流解析为结构化事件，
并桥接到企微的 RabbitMQ 队列协议（LlmChunkMsg）。

包含两套消费逻辑：
- consume_chat_stream: Chat Agent SSE → 文本 delta 桥接
- consume_flow_stream: Flow Agent SSE → 结构化进度桥接
- iter_sse_lines: 公共 SSE 行解析生成器
"""

from __future__ import annotations

import json
import time
from logging import getLogger
from typing import TYPE_CHECKING, Generator

from ag_ui.core.events import EventType

from .context import CHUNK_FLUSH_THRESHOLD, THINKING_MSG, LlmChunkMsg
from .formatters import handle_flow_custom_event

if TYPE_CHECKING:
    from ..utils.rabbitmq import RabbitMQClient

logger = getLogger(__name__)


def _is_thinking_placeholder(content: str) -> bool:
    return content == THINKING_MSG


def _ensure_stream_started(stream_started: bool, stream_id: str, rabbitmq_client: "RabbitMQClient") -> bool:
    if stream_started:
        return True
    LlmChunkMsg(stream_id=stream_id).append_to_cache(rabbitmq_client)
    return True


def iter_sse_lines(stream_generator: Generator, stream_id: str) -> Generator[dict, None, None]:
    """
    从 SSE 流中逐行解析 JSON 数据。

    处理 buffer 拼接、行分割、JSON 解析等通用逻辑，
    调用方只需关注业务语义的事件处理。

    Yields:
        解析后的 JSON dict

    Raises:
        RuntimeError: chunk 处理异常时包装抛出
    """
    buffer = ""
    for chunk in stream_generator:
        try:
            chunk_str = chunk.decode("utf-8", errors="ignore") if isinstance(chunk, bytes) else str(chunk)
            buffer += chunk_str
            lines = buffer.split("\n")
            buffer = lines[-1]
            for line in lines[:-1]:
                line = line.strip()
                if not line or line == "data: [DONE]" or not line.startswith("data: "):
                    continue
                data_content = line[6:]
                if not data_content:
                    continue
                try:
                    yield json.loads(data_content)
                except json.JSONDecodeError:
                    logger.debug(f"stream_id:{stream_id} SSE JSON 解析跳过: {data_content[:100]}")
        except Exception as e:
            raise RuntimeError(f"SSE chunk 处理异常: {e}") from e

    # 处理 buffer 中剩余内容
    remainder = buffer.strip()
    if remainder and remainder.startswith("data: "):
        data_content = remainder[6:]
        if data_content and data_content != "[DONE]":
            try:
                yield json.loads(data_content)
            except json.JSONDecodeError:
                pass


def consume_chat_stream(
    stream_generator: Generator,
    stream_id: str,
    start_time: float,
    rabbitmq_client: RabbitMQClient,
) -> None:
    """消费 Chat Agent SSE 流并桥接到企微 RabbitMQ 队列。

    事件映射：
    - TEXT_MESSAGE_CONTENT → content
    - THINKING_TEXT_MESSAGE_CONTENT → think_content
    - CUSTOM → 提取引用文档 metadata
    - RUN_ERROR → 错误消息终止
    """
    docs: list[dict] = []
    llm_chunk = LlmChunkMsg(content="", is_finish=False, stream_id=stream_id)
    added_content = ""
    think_content = ""
    first_logged = False
    stream_started = False

    try:
        for chunk_json in iter_sse_lines(stream_generator, stream_id):
            if not first_logged:
                first_logged = True
                logger.info(f"stream_id:{stream_id} chat 首次响应耗时: {time.time() - start_time:.3f}s")

            event_type = chunk_json.get("type", "")

            if event_type == EventType.TEXT_MESSAGE_CONTENT:
                text_content = chunk_json.get("delta", "")
                if _is_thinking_placeholder(text_content):
                    continue
                stream_started = _ensure_stream_started(stream_started, stream_id, rabbitmq_client)
                added_content += text_content
                if think_content:
                    llm_chunk.think_content = llm_chunk.think_content + think_content
                    llm_chunk.append_to_cache(rabbitmq_client)
                    think_content = ""
                if len(added_content) > CHUNK_FLUSH_THRESHOLD:
                    llm_chunk.content = llm_chunk.content + added_content
                    llm_chunk.append_to_cache(rabbitmq_client)
                    added_content = ""

            elif event_type == EventType.THINKING_TEXT_MESSAGE_CONTENT:
                think_text = chunk_json.get("delta", "")
                if _is_thinking_placeholder(think_text):
                    continue
                stream_started = _ensure_stream_started(stream_started, stream_id, rabbitmq_client)
                think_content += think_text
                if len(think_content) > CHUNK_FLUSH_THRESHOLD:
                    llm_chunk.think_content = llm_chunk.think_content + think_content
                    llm_chunk.append_to_cache(rabbitmq_client)
                    think_content = ""

            elif event_type == EventType.CUSTOM:
                for doc_info in chunk_json.get("documents", []):
                    if isinstance(doc_info, dict) and "metadata" in doc_info:
                        docs.append(doc_info["metadata"])

            elif event_type == EventType.RUN_ERROR:
                LlmChunkMsg(
                    content=f"处理请求时发生错误: {chunk_json.get('message', chunk_json)}",
                    is_finish=True,
                    stream_id=stream_id,
                ).append_to_cache(rabbitmq_client)
                return

            elif event_type not in (EventType.RAW, EventType.RUN_STARTED, EventType.RUN_FINISHED):
                logger.debug(f"stream_id:{stream_id} chat 忽略事件: {event_type}")

    except RuntimeError as e:
        logger.error(f"stream_id:{stream_id} chat stream 处理错误: {e}")
        LlmChunkMsg(content=f"处理请求时发生错误: {e}", is_finish=True, stream_id=stream_id).append_to_cache(
            rabbitmq_client
        )
        return

    # 刷新剩余内容
    if think_content:
        llm_chunk.think_content = llm_chunk.think_content + think_content
    if added_content:
        llm_chunk.content = llm_chunk.content + added_content
    llm_chunk.is_finish = True
    llm_chunk.docs = docs
    llm_chunk.append_to_cache(rabbitmq_client)


def consume_flow_stream(
    stream_generator: Generator,
    stream_id: str,
    start_time: float,
    rabbitmq_client: RabbitMQClient,
    session_code: str = "",
) -> None:
    """消费 Flow Agent SSE 流并桥接到企微 RabbitMQ 队列。

    事件映射：
    - CUSTOM → 委托给 flow_formatters 处理
    - RUN_ERROR → 错误消息终止
    - RUN_FINISHED → 兜底 finish
    """
    llm_chunk = LlmChunkMsg(content="", is_finish=False, stream_id=stream_id)
    first_logged = False

    try:
        for chunk_json in iter_sse_lines(stream_generator, stream_id):
            if not first_logged:
                first_logged = True
                logger.info(f"stream_id:{stream_id} flow 首次响应耗时: {time.time() - start_time:.3f}s")

            event_type = chunk_json.get("type", "")

            if event_type == EventType.CUSTOM:
                handle_flow_custom_event(
                    chunk_json.get("name", ""),
                    chunk_json,
                    llm_chunk,
                    rabbitmq_client,
                    session_code=session_code,
                )

            elif event_type == EventType.RUN_ERROR:
                LlmChunkMsg(
                    content=f"流程执行出错: {chunk_json.get('message', '未知错误')}",
                    is_finish=True,
                    stream_id=stream_id,
                ).append_to_cache(rabbitmq_client)
                return

            elif event_type == EventType.RUN_FINISHED:
                if not llm_chunk.is_finish:
                    llm_chunk.is_finish = True
                    llm_chunk.append_to_cache(rabbitmq_client)

    except RuntimeError as e:
        logger.error(f"stream_id:{stream_id} flow stream 处理错误: {e}")
        LlmChunkMsg(content=f"流程处理异常: {e}", is_finish=True, stream_id=stream_id).append_to_cache(rabbitmq_client)
