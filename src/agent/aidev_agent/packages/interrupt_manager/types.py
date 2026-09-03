# -*- coding: utf-8 -*-
"""interrupt_manager 统一中断机制的**目标类型落位**（枚举/容器/契约 Protocol 全集中）。

本模块承载中断机制的类型集中（D-05「接口 + 引擎 + 类型实现全集中」的
类型部分，原 ``registry.py`` 纯 Protocol 声明文件已并入本模块）：

- :class:`InterruptReason` —— 中断 reason 字符串枚举（``aidev:tool_approval`` /
  ``aidev:user_question``），配套模块级 reason 常量向后兼容。
- :class:`ProcessorContext` / :class:`InterruptOutcome` / :class:`DispatchResult` /
  :class:`ResumeInputResult` —— 编排层 ctx 与三接口结构化返回容器（45-02）。
- :class:`InterruptStrategy` / :class:`InterruptHandler`（原 ``StreamInterruptHandler``）
  —— 两段纯 Protocol 契约（抛出层策略 + per-reason 对偶单元）。**只声明契约、
  不承载实现与注册**：reason → handler 的绑定由装配层（chat.py execute 入口）
  以 ``InterruptProcessor(handlers={reason: handler})`` dict 显式注入（D-03）。

设计约束（对齐 D-08）：
- 内部数据类型对齐 DB 消息序列统一模型（role/content/builtin_property），
  转换成 AG-UI 消息留在 core/ag_ui 层，故本包**不 import** ag_ui 相关类型。
- **Harness 红线**：本包禁止 ``from aidev_agent.core`` / ``from aidev_agent.services``
  / ``from aidev_agent.api``。所有跨层外部类型（``ToolCallRequest`` / LangGraph
  ``Interrupt`` / ChatPrompt 等）一律以 ``object`` / ``Any`` 鸭子类型承接。

Harness 依赖方向：本模块仅依赖标准库（enum/dataclasses/typing），无跨层 import。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class InterruptReason(str, Enum):
    """中断 reason 的统一枚举落位（值即现有 reason 字符串）。

    驱动 reason → handler / resume policy 的注册表分发，使新增中断类型
    只需注册三段实现即可，零改动主流程。

    继承 ``str`` 保证 ``InterruptReason.TOOL_APPROVAL == "aidev:tool_approval"``
    为 ``True``，与既有 reason 字符串常量天然兼容。
    """

    #: 工具调用审批中断（ITSM 建单），源常量 ``TOOL_APPROVAL_REASON``
    TOOL_APPROVAL = "aidev:tool_approval"
    #: 向用户提问中断，源常量 ``ASK_USER_QUESTION_REASON``
    USER_QUESTION = "aidev:user_question"


# ---------------------------------------------------------------------- #
# 向后兼容的模块级 reason 常量（43-03 迁移收敛）
# ---------------------------------------------------------------------- #
# 源模块（core/nodes/tool/approval_wrapper.py / 原 ag_ui 侧 ask_user_question 常量，
# 后者已随 43-07 shim 移除，单源落位本包）
# 的旧字符串常量在 43-03 迁移时收敛到 :class:`InterruptReason` 枚举。以下两个
# 模块级名字绑定到枚举成员（值即字符串），保留向后兼容，包内与既有消费方
# （``from ...interrupt_manager.types import TOOL_APPROVAL_REASON``）可直接引用。

#: 工具调用审批中断 reason（= ``InterruptReason.TOOL_APPROVAL``）
TOOL_APPROVAL_REASON = InterruptReason.TOOL_APPROVAL
#: 向用户提问中断 reason（= ``InterruptReason.USER_QUESTION``）
ASK_USER_QUESTION_REASON = InterruptReason.USER_QUESTION

#: 建单失败标记（D-15）：approval interrupt value / metadata 命中此字段视为
#: rejected 短路（coordinator gather）或建单降级标记（流结束 prepare）。
CREATE_TICKET_ERROR = "create_ticket_error"


# ---------------------------------------------------------------------- #
# 45-02：ctx 鸭子对象 + 三接口结果容器（方案二 D-01 落地）
# ---------------------------------------------------------------------- #
# 本包 packages 层不 import core/services/api（D-04 红线）。以下容器为**纯数据 /
# 鸭子类型**：承载跨层传递的运行时状态（ctx）与三接口（dispatch_interrupts /
# resolve_resumes / on_resume）的结构化返回结果。ChatPrompt / LangGraph Command
# 等外部类型一律以 ``Any`` 承载（getattr 鸭子访问），装配层（services）负责构造
# 真实对象，packages 层只产数据 dict / 容器。


@dataclass
class ProcessorContext:
    """dispatch_interrupts / resolve_resumes 的显式运行时状态（ctx 鸭子对象）。

    装配层（agent.py / chat.py）从 ``active_run`` + ``input.messages`` +
    ``execute_kwargs`` 现场拼装，本包只声明鸭子字段（不 import services 类型）。

    - ``chat_history`` 元素为 services 层 ChatPrompt 鸭子对象（getattr 访问
      content / builtin_property / role / id，先例 ask_user_question.py 跨层鸭子手法）。
    - ``tasks`` 为 graph ``state.tasks``（含各 pending interrupt 的 task 对象），
      resolve_resumes 收编 approval 门禁与 ask_user 过滤时使用。
    - ``spawn_context`` 为场景④（子 Agent 中断冒泡）扩展位（D-15），仅签名不实现。
    """

    session_code: str = ""
    thread_id: str = ""
    run_id: str = ""
    executor: str | None = None
    # [deprecated] U-04 废除，Plan 03 随 agent.py 迁移删除；get_resume_input 内部自推导。
    # 调用方传入终态集合概念整体废除，本字段仅为 Plan 03 前 agent.py 传参兼容而保留。
    terminal_interrupt_ids: set[str] | None = None
    chat_history: list[Any] | None = None
    turn_id: str | None = None
    input_text: str | None = None
    #: graph state.tasks（含各 pending interrupt 的 task 对象）；resolve_resumes
    #: 收编 approval 门禁 + ask_user 过滤的 graph tasks 源
    tasks: list[Any] | None = None
    #: 场景④ 扩展位（D-15）：子 Agent 中断冒泡预留，仅签名不实现
    spawn_context: dict[str, Any] | None = None


@dataclass
class InterruptOutcome:
    """dispatch_interrupts 的逐项结果（原始 intr 对象 + 逐项状态标注）。

    ``status`` 字面量固定为 ``built`` / ``gated`` / ``terminal_skipped`` /
    ``prepare_failed``，装配层据此串行裁剪（一次一卡）。intr 为**原始** interrupt
    对象（零处理，D-09），id 与 value 彻底分离。
    """

    intr: Any  #: 原始 intr 对象（零处理）
    reason: str | None = None
    status: str = "built"  #: "built" | "gated" | "terminal_skipped" | "prepare_failed"
    builtin_property: dict[str, Any] | None = None  #: prepare 产物（approval enrich 落库字段）
    replay_payload: dict[str, Any] | None = None  #: 回放 payload（build_replay 雏形）


@dataclass
class DispatchResult:
    """dispatch_interrupts 的返回容器（全量 + 逐项状态标注）。"""

    interrupts: list[InterruptOutcome] = field(default_factory=list)


@dataclass
class ResumeInputResult:
    """get_resume_input 的返回容器（D-06/D-16，承载串行推进产物）。

    ``command`` 用 ``Any`` 承载（LangGraph Command 属外部类型，packages 层不
    import）。``ready=True`` 表示全 pending 已完成 → ``command`` 为
    ``Command(resume=...)`` 且回放三字段（``approve_result`` /
    ``approval_interrupts`` / ``ask_user_question_interrupts``）已就绪（D-06，
    Agent 构造前就绪，F.4 #1）。``ready=False`` → ``next_interrupt`` 为首个未完成
    interrupt，装配层据此决策（chat 层 D-09 直接构造 SSE 下发卡片）。

    - ``approve_result``：首个已终态 approval 单元的 DB 权威 action。
    - ``approval_interrupts``：DB 权威元素列表（逐元素 hydrate 后）。
    - ``ask_user_question_interrupts``：经 ``filter_ask_user_question_interrupts``
      graph-tasks 源过滤（D-06）。
    - ``propagated_from``：场景④ 扩展位（D-15），仅签名不实现。
    """

    ready: bool = False
    #: 全就绪时 Command(resume=...)
    command: Any | None = None
    #: 未就绪时首个未完成 interrupt
    next_interrupt: Any | None = None
    approve_result: str | None = None
    approval_interrupts: list[dict] | None = None
    ask_user_question_interrupts: list[dict] | None = None
    #: 场景④ 扩展位（D-15）：协议级 propagated_from 标注位，仅签名不实现
    propagated_from: dict[str, Any] | None = None


# ---------------------------------------------------------------------- #
# 两段纯 Protocol 契约（原 registry.py 并入，只声明契约、不承载实现与注册）
# ---------------------------------------------------------------------- #


@runtime_checkable
class InterruptStrategy(Protocol):
    """抛出策略辅助（LangGraph 抛出层契约，包内落位）。

    对应 ``core/nodes/tool/approval_wrapper.py`` 的 ``ItsmApprovalStrategy``
    抛出策略（原 ``InterruptionStrategy`` 单方法协议已收敛），per-tool_call 级别。每个策略封装一种中断的触发检测 →
    payload 构造 → interrupt 调用（建单副作用已按 D-01 迁往流结束层
    ``InterruptHandler.prepare``，本层只构造 payload 并抛出）。

    注意：request 为 LangGraph ``ToolCallRequest`` 的鸭子类型，本包为遵守
    harness ``packages -> core`` 红线不 import 该类型，统一用 ``object`` 承接，
    具体实现（``ItsmApprovalStrategy``）在 ``core/nodes/tool/approval_wrapper.py``。
    """

    #: 该策略负责的 reason 字符串（对齐 :class:`InterruptReason` 枚举值）
    reason: str

    def interrupt(self, request: object) -> object:
        """单方法中断策略辅助。

        Args:
            request: ToolCallRequest 鸭子类型对象（包内实现按字段访问）。

        Returns:
            None: 策略无中断或已通过，调用方继续执行。
            非 None: 短路返回消息（如审批拒绝），由调用方决定用途。

        Raises:
            Exception: 策略调 ``langgraph.interrupt(payload)`` 间接抛出，
                图暂停。本层不捕获，交由上层处理。
        """
        ...


@runtime_checkable
class InterruptHandler(Protocol):
    """per-reason 对偶单元（原 ``StreamInterruptHandler``）：流结束处理（``prepare``）
    ↔ resume 校验（``query_resume_status``）↔ resume 写路径（``on_resume``）。

    单一两段 Protocol（D-02 / D-03 / D-05）：方法面对标 ``ApprovalHandler``
    （approval.py）与 ``AskUserQuestionHandler``（ask_user_question.py）：

    - ``prepare`` 流结束侧：DB 全量落库数据 + 活跃中断建单 + enrich（D-01）；
    - ``query_resume_status`` resume 侧：**全员只读门禁**（D-06），approval 委托
      ``query_approval_info_for_interrupt``、ask_user 委托 ``query_answered_status``；
    - ``extract_builtin_property`` 提取落库字段集（D-08：对齐 DB 统一模型）；
    - ``on_resume`` resume 侧写路径（U-02/D-05）：approval **空实现**（审批终态
      由审批平台回调写 DB）；ask_user 执行 chat_history inplace 改写 + 经注入的
      分发方法写 DB。``on_resume`` 返回 None（无编排返回值，事件派发内聚到
      handler 内部，D-16）。

    reason → handler 绑定由装配层以 ``InterruptProcessor(handlers=...)`` dict 注入
    （D-03），本包不承载注册表。
    """

    #: 该 handler 负责的 reason 字符串（对齐 :class:`InterruptReason` 枚举值）
    reason: str

    def prepare(self, interrupt: object, ticket_creator: object | None = None, **ctx: Any) -> object:
        """流结束建单 + enrich 副作用（每个 reason 只执行一次）。

        interrupt 为 LangGraph ``Interrupt`` 鸭子类型（``.id`` / ``.value``，
        对齐 :class:`InterruptStrategy.interrupt(request: object)` 先例，包内不
        import langgraph）。实现**就地 enrich ``interrupt.value``**（可整体替换
        value，如 approval target→payload），**绝不读写 value 内的 id**，返回
        interrupt 对象。

        Args:
            interrupt: LangGraph ``Interrupt`` 鸭子类型对象（``.id`` / ``.value``）。
            ticket_creator: 建单封装（如 ``ItsmTicketCreator``，封装
                resource_manager / username / session_code）。
            **ctx: 运行时 ctx（如 ``thread_id`` / ``run_id``）。

        Returns:
            处理后的 interrupt 对象（enrich 后的 value 就地写回）；异常时按
            实现决定是否记 ``create_ticket_error`` 标记（D-01：中断不因建单
            失败被吞，照发 interrupt）。
        """
        ...

    def query_resume_status(
        self,
        session_code: str,
        pending_interrupt: Any,
        *,
        resource_manager: object | None = None,
    ) -> dict[str, Any]:
        """resume 侧**全员只读门禁**（D-06）：查当前 pending 的就绪状态，返回门禁契约 dict。

        **不写 DB**（读写分离，D-13 精神）：只读 DB 权威记录判当前 pending 是否已
        终态。approval 委托 ``query_approval_info_for_interrupt``；ask_user 委托
        ``query_answered_status``。编排层（processor 聚合循环）统一经
        ``self._handlers[reason]`` 注入的 handler 查表。

        Args:
            session_code: 会话 code（DB 权威记录查询用）。
            pending_interrupt: 当前被门禁的 pending interrupt value dict
                （含 id 或 toolCallId）。编排层聚合循环恒传。
            resource_manager: 鸭子注入（``object | None``，packages 层不 import
                services 类型）；approval 经构造注入忽略该参数。

        Returns:
            对偶单元层门禁契约 dict（``action`` + ``resume_value``，字段名固定）：
            ``resolved``/``approved``/``rejected``/``cancelled``（就绪）或
            ``not_ready``（未就绪，resume_value=None）。
        """
        ...

    def on_resume(self, resume: Any, *, interrupt_messages: Any, **ctx: Any) -> None:
        """resume 侧**写路径**（U-02/D-05，返回 None）。

        对偶单元对单个 resume item 的 on_resume 处理：approval 为空实现（审批
        终态由审批平台回调写 DB，前端直调 user_operation / ITSM 回调，agent 侧
        纯读）；ask_user 执行 chat_history inplace 改写 + 经注入的分发方法写 DB。
        事件派发内聚到 handler 内部（D-16），无编排返回值。

        Args:
            resume: 前端续流 resume item（不可信输入，T-48-01）。由编排层
                （``InterruptProcessor.resolve_resumes``）按 interruptId → 消息 →
                reason 路由后传入。
            interrupt_messages: 该 interrupt_id 命中的 chat_history 消息内容
                （list[dict]），供 handler 按消息内 reason / 内容定位与校验。
            **ctx: 运行时 ctx（``chat_history`` / ``session_code`` / ``thread_id`` /
                ``turn_id`` / ``input_text``）。
        """
        ...

    def extract_builtin_property(
        self,
        interrupt_id: str,
        interrupt: Any,
        graph_thread_id: str | None = None,
    ) -> dict[str, Any]:
        """从 interrupt 提取落库用 ``builtin_property`` 字段集（D-08）。

        Args:
            interrupt_id: interrupt id。
            interrupt: interrupt 对象或 dict。
            graph_thread_id: 可选图线程 id，缺省时由实现按字段兜底。

        Returns:
            落库用的 ``builtin_property`` dict。
        """
        ...


__all__ = [
    "InterruptReason",
    "TOOL_APPROVAL_REASON",
    "ASK_USER_QUESTION_REASON",
    "CREATE_TICKET_ERROR",
    "ProcessorContext",
    "InterruptOutcome",
    "DispatchResult",
    "ResumeInputResult",
    "InterruptStrategy",
    "InterruptHandler",
]
