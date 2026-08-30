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

from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.agent.approval import ApprovalStateHandler

from aidev_bkplugin.services.agent_builder import AgentBuilder
from aidev_bkplugin.services.agent_execution import AgentExecutor
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

    # 1. 轮询是否需要续流（ITSM 回调后 is_resume 返回 True），无超时，收到回调前持续轮询
    handler = ApprovalStateHandler()
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
    try:
        resume_items = []
        for interrupt in interrupts:
            if not isinstance(interrupt, dict):
                continue
            interrupt_id = interrupt.get("id") or interrupt.get("interruptId")
            if not interrupt_id:
                continue
            # status / payload.approved 由 hydrate_resume_payload 根据三态统一填充
            resume_items.append({"interruptId": interrupt_id})

        if not resume_items:
            logger.warning(
                "[ApprovalResume] 缺少 interrupts，无法构造标准 resume items: session_code=%s",
                session_code,
            )
            return

        ApprovalStateHandler.hydrate_resume_payload(resume_items, approve_result)

        builder = AgentBuilder(username=username)
        agent_instance = builder.by_session_code(session_code)

        execute_kwargs = ExecuteKwargs(
            stream=True,
            session_code=session_code,
            thread_id=graph_thread_id,
            resume=resume_items,
            # 后台 drain（无 SSE 下游，下方 for _ in generator 自行排空）：标记 background_only，
            # 使消费者读到 EOD 时不立即清理队列，保留缓存历史供前端在清理窗口内接管续流。
            background_only=True,
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
