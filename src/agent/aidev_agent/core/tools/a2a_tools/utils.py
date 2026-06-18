# -*- coding: utf-8 -*-
"""a2a_tools 包内共享工具。

放置 LocalBackend / BkAiBackend 等后端共用的内联等价物，避免重复实现并
规避 Harness ``tools → nodes`` 禁止依赖（不导入 ``core/nodes/pv.py``）。

共享函数：
- ``extract_session_pv_volume_id`` / ``extract_child_execute_kwargs``：子 Agent
  execute_kwargs 构造（身份字段继承、spawn_depth 递增、PV 注入等）
- ``parse_sse`` / ``consume_sse_stream``：SSE 解析与流式循环（事件累积、
  心跳回调、error 事件统一 raise、tool_count 递增统计）
- ``detect_intermediate_step`` / ``sanitize_error_message`` / ``build_enriched_result``：
  流式事件步骤描述、错误脱敏、标准化富结果构建（原 progress.py 合并而来）
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable
from logging import getLogger
from typing import Any

from aidev_agent.core.tools.a2a_tools.types import AgentResult, ExitReason
from aidev_agent.pydantic_models import ExecuteKwargs

logger = getLogger("aidev-agent")


def extract_session_pv_volume_id(state: Any | None) -> str | None:
    """从 LangGraph state 中提取第一条 session 级 paas-sbx-pv 的 volume_id。

    Per D-10: filter by mount_path=="session" + type=="paas-sbx-pv" (inline equivalent of
    pv.py `_is_session_pv`, NOT imported to avoid the prohibited tools→nodes dependency).
    Per D-11: does not distinguish source (runtime or platform both injected).

    Args:
        state: LangGraph state dict, may be None; reads state["runtime_paas_sbx_pv"].

    Returns:
        第一条匹配的 volume_id；无匹配时返回 None。
    """
    state_pv = (state or {}).get("runtime_paas_sbx_pv", []) if isinstance(state, dict) else []
    return next(
        (
            pv.get("volume_id")
            for pv in (state_pv or [])
            if pv.get("type") == "paas-sbx-pv" and pv.get("mount_path") == "session" and pv.get("volume_id")
        ),
        None,
    )


def parse_sse(line: str) -> dict[str, Any] | None:
    """解析单行 SSE 编码数据。

    LocalBackend / BkAiBackend 共用同一套 SSE 解析逻辑：
    ``data: <json>`` + ``data: [DONE]``。提取为共享函数避免两后端重复实现。
    仅依赖标准库，不依赖 core/nodes（符合依赖方向）。

    Args:
        line: SSE 编码行，格式为 ``data: <json>`` 或 ``data: [DONE]``

    Returns:
        解析后的事件 dict；非 data 行、[DONE] 行或无法解析的 JSON 返回 None
    """
    if not line.startswith("data: "):
        return None
    data_str = line[6:]
    if data_str.strip() == "[DONE]":
        return None
    try:
        return json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None


def extract_child_execute_kwargs(
    config: Any,
    *,
    state: Any | None = None,
    session_code: str = "",
    stream: bool = True,
    caller_bk_app_code: str = "",
    invoke_timeout: int | None = None,
) -> ExecuteKwargs:
    """从 config 中提取主 Agent 的 execute_kwargs 并构造子 Agent 的 execute_kwargs 对象。

    LocalBackend / BkAiBackend 共用的子 Agent execute_kwargs 构造逻辑：
    - D-08: 返回类型为 ExecuteKwargs 对象；调用方在构造远程 payload 时再 model_dump()。
    - D-04: 显式重置 thread_id 避免父子串扰（APIGW 会话字段，非身份字段）。
    - D-03: 身份字段（executor/caller_*）由 model_copy() 全量继承，不重置。
    - D-09/D-10/D-11/D-12: 从 state 读 session 级 PV 注入 sandbox_pv_id。

    Args:
        config: 运行时配置，可包含 configurable.execute_kwargs
        state: 父 Agent 的 LangGraph state，从中读取 runtime_paas_sbx_pv 注入 sandbox_pv_id
        session_code: 子 Agent 的会话 code
        stream: 是否启用流式模式，默认 True
        caller_bk_app_code: 调用方 app_code（从 spec.params 获取）
        invoke_timeout: 子 Agent 执行超时秒数；非 None 时写入 invoke_timeout 字段。
            LocalBackend 传入 ``spec.timeout_seconds``；BkAiBackend 不传（超时由 HTTP 层控制）。

    Returns:
        构造好的 ExecuteKwargs 对象
    """
    base = ExecuteKwargs()
    if config and isinstance(config, dict):
        ek = config.get("configurable", {}).get("execute_kwargs")
        if ek and isinstance(ek, ExecuteKwargs):
            base = ek.model_copy()
            # D-04/D-08: 深度递增 — 子 = 父 + 1，spawned_by 记录父会话
            base.spawn_depth = ek.spawn_depth + 1
            base.spawned_by = ek.session_code

    base.stream = stream
    base.persist_input = True
    base.session_code = session_code
    if caller_bk_app_code:
        base.caller_bk_app_code = caller_bk_app_code
    if invoke_timeout is not None:
        base.invoke_timeout = invoke_timeout

    # D-04: 显式重置 thread_id，避免子 Agent APIGW 调用误用父 thread_id（会话串扰）
    base.thread_id = None

    # D-09/D-10/D-11/D-12: 从 state 读 session 级 PV，注入 sandbox_pv_id
    volume_id = extract_session_pv_volume_id(state)
    if volume_id:
        base.sandbox_pv_id = volume_id

    return base


def consume_sse_stream(
    lines: Iterable[str | bytes],
    *,
    progress_callback: Any = None,
    emit_elapsed: bool = False,
) -> tuple[str, list[dict[str, Any]], int]:
    """迭代 SSE 流，累积文本结果和事件列表，发送心跳回调。

    LocalBackend._run_subagent / BkAiBackend._run_subagent
    共用的流式循环逻辑。本函数仅负责「解析 + 累积 + 回调」三件事，
    不负责 payload 构造、HTTP 请求、响应生命周期管理、非流式兜底
    （这些由各 backend 自行处理）。

    统一行为（修复两边历史不一致）：
    - 非 dict 事件（如 JSON 解析出 list/str）跳过（Local 历史版本漏掉）
    - error 事件无条件 raise RuntimeError（Local 历史版本漏掉 — 已确认是 bug）
    - elapsed_seconds 字段按需发送（仅 BkAi 需要；Local 不发）
    - tool_count 维护递增计数器（替代原 count_tool_calls 每次 O(n) 扫描，
      修复长流的 O(n²) 性能问题）

    Args:
        lines: SSE 行迭代器，元素可为 str 或 bytes（bytes 自动 utf-8 解码）
        progress_callback: 可选心跳回调，发送 ``subagent.intermediate_steps``
            和 ``subagent.heartbeat`` 事件；为 None 时跳过
        emit_elapsed: 是否在 heartbeat 中附带 ``elapsed_seconds`` 字段。
            BkAi 远程路径需要该字段做超时监控；Local 本地路径不需要。

    Returns:
        ``(result_text, events, tool_count)``：最后一轮 TEXT_MESSAGE 拼接的文本、
        完整事件列表、TOOL_CALL_START 事件累计次数（供 build_enriched_result
        的 tool_calls 参数直接使用）

    Raises:
        RuntimeError: 收到 type=="error" 的 SSE 事件时抛出（由调用方的
            统一 except 处理，转换为 failed 结果）
    """
    text_parts: list[str] = []
    events: list[dict[str, Any]] = []
    tool_count = 0
    start_time = time.time() if emit_elapsed else None

    for raw in lines:
        line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        event = parse_sse(line)
        if event is None:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)

        event_type = event.get("type")
        if event_type == "TEXT_MESSAGE_START":
            text_parts.clear()
        elif event_type == "TEXT_MESSAGE_CONTENT":
            delta = event.get("delta", "")
            if isinstance(delta, str):
                text_parts.append(delta)
        elif event_type == "TOOL_CALL_START":
            tool_count += 1
        elif event_type == "error":
            raise RuntimeError(event.get("error", "Unknown stream error"))

        if progress_callback:
            step_content = detect_intermediate_step(event, events)
            if step_content:
                progress_callback("subagent.intermediate_steps", content=step_content)
            heartbeat_kwargs: dict[str, Any] = {
                "tool_count": tool_count,
                "iteration": len(events),
            }
            if emit_elapsed and start_time is not None:
                heartbeat_kwargs["elapsed_seconds"] = round(time.time() - start_time, 3)
            progress_callback("subagent.heartbeat", **heartbeat_kwargs)

    return "".join(text_parts), events, tool_count


# ==================== 流式事件步骤 / 错误脱敏 / 富结果构建 ====================


def detect_intermediate_step(event: dict[str, Any], all_events: list[dict[str, Any]]) -> str | None:
    """从 SSE 事件中检测子 Agent 执行步骤变更。

    根据事件类型返回对应的中文描述，用于通过 progress_callback("subagent.intermediate_steps")
    通知前端当前子 Agent 执行状态。

    Args:
        event: 当前 SSE 事件
        all_events: 截至当前的所有 SSE 事件列表（用于计算工具执行次序）

    Returns:
        步骤描述文本，无法识别时返回 None
    """
    event_type = event.get("type", "")

    if event_type == "TOOL_CALL_START":
        tool_name = event.get("toolCallName", "unknown")
        tool_count = sum(1 for e in all_events if e.get("type") == "TOOL_CALL_START")
        return f"正在执行工具 (第{tool_count}次, {tool_name})"

    if event_type == "TEXT_MESSAGE_START":
        return "正在进行模型输出"

    if event_type == "CUSTOM":
        name = event.get("name", "")
        if name.startswith("knowledge_rag"):
            return "正在进行知识库召回"

    return None


def sanitize_error_message(message: str) -> str:
    """过滤错误消息中的敏感信息。

    移除以下模式（D-10）：
    - API key (sk- 前缀长字符串)
    - OpenAI 项目级 key (sk-proj- 前缀)
    - access_token 参数值
    - access_token 的 URL 编码形式 (access_token%3D)
    - Bearer token
    - Bearer token 的 URL 编码形式 (Bearer%20)
    - 蓝鲸凭证 bk_token / app_secret / app_code（含 URL 编码变体）

    Args:
        message: 原始错误消息

    Returns:
        脱敏后的错误消息
    """
    sanitized = message
    # 移除 API key 模式 (sk- 前缀)
    sanitized = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_API_KEY]", sanitized)
    # 移除 access_token 参数值
    sanitized = re.sub(r'access_token[=:]\s*["\']?[a-zA-Z0-9_-]{10,}["\']?', "access_token=[REDACTED]", sanitized)
    # 移除 Bearer token
    sanitized = re.sub(r"Bearer\s+[a-zA-Z0-9_\-.]{20,}", "Bearer [REDACTED]", sanitized)
    # D-10: 移除 OpenAI 项目级 key (sk-proj- 前缀，含连字符)
    sanitized = re.sub(r"sk-proj-[a-zA-Z0-9_-]{20,}", "[REDACTED_API_KEY]", sanitized)
    # D-10: 移除 URL 编码的 access_token (access_token%3D)
    sanitized = re.sub(r"access_token%3D[a-zA-Z0-9%_\-]{10,}", "access_token=[REDACTED]", sanitized)
    # D-10: 移除蓝鲸 bk_token
    sanitized = re.sub(r'bk_token[=:]\s*["\']?[a-zA-Z0-9_-]{10,}["\']?', "bk_token=[REDACTED]", sanitized)
    # D-10: 移除蓝鲸 app_secret
    sanitized = re.sub(r'app_secret[=:]\s*["\']?[a-zA-Z0-9_-]{10,}["\']?', "app_secret=[REDACTED]", sanitized)
    # D-10: 移除蓝鲸 app_code
    sanitized = re.sub(r'app_code[=:]\s*["\']?[a-zA-Z0-9_-]{3,}["\']?', "app_code=[REDACTED]", sanitized)
    # D-10: 移除 URL 编码的 bk_token (bk_token%3D)
    sanitized = re.sub(r"bk_token%3D[a-zA-Z0-9%_\-]{10,}", "bk_token=[REDACTED]", sanitized)
    # D-10: 移除 URL 编码的 app_secret (app_secret%3D)
    sanitized = re.sub(r"app_secret%3D[a-zA-Z0-9%_\-]{10,}", "app_secret=[REDACTED]", sanitized)
    # D-10: 移除 URL 编码的 app_code (app_code%3D)
    sanitized = re.sub(r"app_code%3D[a-zA-Z0-9%_\-]{3,}", "app_code=[REDACTED]", sanitized)
    # D-10: 移除 URL 编码的 Bearer token (Bearer%20)
    sanitized = re.sub(r"Bearer%20[a-zA-Z0-9%_\-.]{20,}", "Bearer [REDACTED]", sanitized)
    return sanitized


def build_enriched_result(
    *,
    status: str,
    agent_name: str = "",
    agent_type: str = "",
    summary: str | None = None,
    error: str | None = None,
    tool_calls: int = 0,
    exit_reason: str = ExitReason.COMPLETED.value,
) -> AgentResult:
    """构建标准化富结果。

    Phase 26：返回 AgentResult(BaseModel) 替代 dict。移除 duration_seconds / session_code / member_name，
    这些属于 provider 层概念。duration_seconds 由 timer_wrapper 在 ToolNode 层统一记录。

    Args:
        status: 执行状态 ("completed" | "failed")
        agent_name: Agent 名称（仅用于日志，不写入 AgentResult）
        agent_type: 智能体后端类型（如 bkai / local）
        summary: 完成时的文本结果
        error: 失败时的错误信息（会自动脱敏）
        tool_calls: 工具调用次数
        exit_reason: 退出原因（ExitReason 枚举值）

    Returns:
        AgentResult 标准化富结果
    """
    if error:
        error = sanitize_error_message(error)

    result = AgentResult(
        status=status,
        agent_type=agent_type,
        result=summary or "",
        tool_calls=tool_calls,
        exit_reason=exit_reason,  # type: ignore[arg-type]  # str 与 ExitReason 兼容
    )
    if error:
        result = result.model_copy(update={"error": error})
    return result
