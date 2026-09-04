# -*- coding: utf-8 -*-
"""审批完成后台自动续流。

当 Agent 因工具审批中断时，启动后台工作线程轮询审批结果，
收到 ITSM 回调前持续轮询（不设超时），审批完成后自动续流，无需前端在线。

设计思路：
- 利用 LangGraph 的 interrupt/resume 机制，后台续流复用 AgentBuilder + execute 基础设施
- 使用 stream=True，事件经由 AGUISessionWriter 写入 DB，与前端续流行为一致
- 如果前端同时续流，ConsumerPreemptedError 会让后台线程优雅退出
"""

import threading
import time
from logging import getLogger

from aidev_agent.services.agent.approval import ApprovalStateHandler
from aidev_agent.utils.tracing import propagated_trace_context, recording_span, trace_headers

from aidev_bkplugin.services.agent_builder import AgentBuilder
from aidev_bkplugin.services.agent_execution import AgentExecutor, build_execute_kwargs
from aidev_bkplugin.services.agent_session import SessionManager

logger = getLogger(__name__)

# 轮询间隔（秒）
_POLL_INTERVAL = 5


def start_approval_resume_worker(
    session_code: str,
    username: str,
    graph_thread_id: str,
    interrupts: list[dict] | None = None,
):
    """启动后台续流工作线程。

    在 BaseSessionWriter.handle_run_finished 检测到 interrupt 时调用。
    """
    thread = threading.Thread(
        target=_approval_resume_worker,
        args=(session_code, username, graph_thread_id, interrupts or []),
        daemon=True,
        name=f"approval-resume-{session_code[:12]}",
    )
    thread.start()
    logger.info(
        "[ApprovalResume] 后台续流线程已启动: session_code=%s, graph_thread_id=%s",
        session_code,
        graph_thread_id,
    )


def _approval_resume_worker(session_code: str, username: str, graph_thread_id: str, interrupts: list[dict]):
    """后台续流工作线程：轮询审批结果，完成后续流。"""
    logger.info(
        "[ApprovalResume] 开始轮询审批结果: session_code=%s, username=%s",
        session_code,
        username,
    )

    # 0. 轮询 handler：ApprovalStateHandler 直连平台 API（U-01 重构后自持数据访问，
    # 不再收 resource_manager），username 预留 X-BKAIDEV-USER header 位。
    # 注意：agent 构造保持在轮询**之后**——chat_history 须在回调落地后加载，
    # 否则 resume 的 terminal_interrupt_ids 判定用的是回调前的陈旧记录，
    # 已批中断不被排除而被重推（UAT：重推未 enrich 的北京审批卡）。
    handler = ApprovalStateHandler(username=username)
    poll_count = 0
    while True:
        poll_count += 1
        if handler.check_resume(session_code):
            logger.info(
                "[ApprovalResume] 审批已回调，准备续流: session_code=%s (第 %d 次轮询)",
                session_code,
                poll_count,
            )
            break
        time.sleep(_POLL_INTERVAL)

    # 2. 从 interrupt 记录的 property 获取审批结果
    approve_info = handler.fetch_approve_result(session_code)
    if approve_info is None:
        logger.warning("[ApprovalResume] 无法获取审批结果，放弃续流: session_code=%s", session_code)
        return
    approve_result = approve_info["approve_result"]

    # 主动取消由调用方根据 user_operation.next 续流（Web 或企微）。
    # 与平台后台 worker 保持一致，避免两个消费者同时恢复同一个中断。
    if approve_result == "cancelled":
        logger.info("[ApprovalResume] 审批已取消，由操作发起方续流: session_code=%s", session_code)
        return

    # 3. 审批完成，构建 agent 并续流
    # 恢复回调落库的父上下文；不要继承轮询线程中可能残留的其他会话 Trace。
    # 上下文覆盖生成器构造和排空，保证延迟发布的恢复事件也关联到审批回调。
    with (
        propagated_trace_context(approve_info.get("approval_trace_context")),
        recording_span("bkplugin.approval.resume", record_exception=False, use_global_tracer=True),
    ):
        _resume_approval(session_code, username, graph_thread_id, interrupts, approve_info)


def _resume_approval(
    session_code: str,
    username: str,
    graph_thread_id: str,
    interrupts: list[dict],
    approve_info: dict,
) -> None:
    """审批回调后构建 agent 并后台续流（须在回调 trace 上下文内调用）。

    Args:
        session_code: 会话码。
        username: 会话主人（续流执行身份）。
        graph_thread_id: 图线程 id。
        interrupts: 触发续流的 pending interrupts（来自 pending_interrupt 上下文）。
        approve_info: ``ApprovalStateHandler.fetch_approve_result`` 富返回，
            含 ``approve_result`` 与本回调已终态审批的 ``interrupts``。
    """
    approve_result = approve_info["approve_result"]

    try:
        # 串行语义：只 resume 本回调已终态的审批（approve_info.interrupts 元素 id
        # 即该审批的 interrupt id）。其余 pending（工单未建/未回调）保持挂起——
        # 全量 hydrate 会把未批的审批也标记 approved，串行门禁会拦下整个 resume，
        # 图不拉起、下一张工单永远建不出来（UAT：第二次审批死锁）。
        approved_ids = {
            element.get("id")
            for element in (approve_info.get("interrupts") or [])
            if isinstance(element, dict) and element.get("id")
        }
        resume_items = []
        for interrupt in interrupts:
            if not isinstance(interrupt, dict):
                continue
            interrupt_id = interrupt.get("id") or interrupt.get("interruptId")
            if not interrupt_id:
                continue
            if approved_ids and interrupt_id not in approved_ids:
                continue  # 非本回调审批：保持挂起，等其自身工单终态
            # status / payload.approved 由 hydrate_resume_payload 根据三态统一填充
            resume_items.append({"interruptId": interrupt_id})

        if not resume_items:
            logger.warning(
                "[ApprovalResume] 缺少 interrupts，无法构造标准 resume items: session_code=%s",
                session_code,
            )
            return

        ApprovalStateHandler.hydrate_resume_payload(resume_items, approve_result)

        # 回调后构建 agent：chat_history 加载到回调后的最新记录（含已批终态），
        # resume 侧 terminal 判定 / enrich 复用才能拿到正确数据
        builder = AgentBuilder(username=username)
        agent_instance = builder.by_session_code(session_code)

        # 与 chat 一样走 build_execute_kwargs：用 username 补齐 executor / caller_executor。
        # caller_bk_* 只保留入参（本路径未传则保持空）。审批人仍来自工具配置
        # target.approval.approvers，不会把调用人当成审批人。
        execute_kwargs = build_execute_kwargs(
            {
                "stream": True,
                "session_code": session_code,
                "thread_id": graph_thread_id,
                "resume": resume_items,
                "caller_trace_context": trace_headers(),
                "background_only": True,
            },
            username,
        )

        logger.info(
            "[ApprovalResume] 开始后台续流: session_code=%s, approve_result=%s",
            session_code,
            approve_result,
        )

        # 使用 stream=True + execute_with_save，事件经由 AGUISessionWriter 写入 DB
        session_manager = SessionManager(username=username)
        generator = AgentExecutor(session_manager).execute_with_save(
            agent_instance,
            execute_kwargs,
            session_code,
        )

        # 消费生成器，触发事件回写
        for _ in generator:
            pass

        logger.info("[ApprovalResume] 后台续流完成: session_code=%s", session_code)

    except Exception:
        logger.exception("[ApprovalResume] 后台续流失败: session_code=%s", session_code)
