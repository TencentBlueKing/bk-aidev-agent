# -*- coding: utf-8 -*-
"""轮次产物识别（artifacts_generated）业务实现。

分层定位：本模块属于 `services/agent/` 业务层，承载：

1. **PV 语义判定**：从 `runtime_paas_sbx_pv` state 判断是否存在会话级 PaaS 沙箱 PV
2. **PaaS list_files 结果 → artifact 转换**：把 PaaS 返回的文件条目映射为前端消费的 artifact 字段
3. **RUN_FINISHED 前 hook 组装**：通过 :func:`build_artifacts_generated_hook` 生成一个签名
   与 :meth:`LangGraphAGUIAgent._emit_run_end_extras` 兼容的 async generator，供
   `AidevAGUIAgent(run_end_extras_hook=...)` 注入

设计要点：
- `core/ag_ui/` 只保留通用 hook 扩展点，不知道 `resource_manager` / `executor_info` 等业务凭证
- hook 内部异常兜底：PaaS 抛错时 `logger.warning` 后 return，不阻断 RUN_FINISHED
- `resource_manager is None` 时 hook 退化为空 async generator（不 emit 任何事件）
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from logging import getLogger
from typing import Any, Callable

from ag_ui.core import BaseEvent, CustomEvent, EventType

from aidev_agent.core.ag_ui.types import SessionPersistenceEventNames, State
from aidev_agent.services.sandbox_pv_files import SandboxPvFileService

logger = getLogger(__name__)


# hook 通过 dispatch_event 触发协议层事件分发（DB writer + SSE），而不是自行 emit
DispatchEvent = Callable[[BaseEvent], Any]
RunEndExtrasHook = Callable[..., AsyncGenerator[Any, None]]


def _has_session_pv(state_values: State) -> bool:
    """是否存在会话级 paas 沙箱 PV。

    判定条件：``runtime_paas_sbx_pv`` 列表中至少存在一条同时满足：
    - ``type == "paas-sbx-pv"``
    - ``mount_path == "session"``
    - ``volume_id`` 非空
    """
    pvs = state_values.get("runtime_paas_sbx_pv") or []
    return any(
        pv.get("type") == "paas-sbx-pv" and pv.get("mount_path") == "session" and pv.get("volume_id")
        for pv in pvs
    )


def _files_to_artifacts(files: list[dict]) -> list[dict]:
    """PaaS ``list_files`` 结果 → artifacts 列表。``outputId`` 即文件 ``path``。

    过滤：
    - ``is_dir=True`` 的目录条目
    - ``path`` 为空的异常条目

    字段映射：
    - ``outputId``: 原始 ``path``
    - ``type``: 文件后缀（小写），无后缀时为 ``"file"``
    - ``name``: 优先取 ``name``，缺失时用 ``path`` 最后一段兜底
    - ``size``: 原样透传，缺失时为 ``0``
    """
    artifacts: list[dict] = []
    for f in files:
        if f.get("is_dir"):
            continue
        path = f.get("path") or ""
        if not path:
            continue
        name = f.get("name") or path.rsplit("/", 1)[-1]
        suffix = name.rsplit(".", 1)[-1].lower() if "." in name else "file"
        artifacts.append(
            {
                "outputId": path,
                "type": suffix,
                "name": name,
                "size": f.get("size", 0),
            }
        )
    return artifacts


def build_artifacts_generated_hook(
    resource_manager: Any,
    executor_info: dict | None,
) -> RunEndExtrasHook:
    """构造 RUN_FINISHED 前的产物识别 hook。

    hook 签名（全 keyword-only，未来加字段不破坏兼容）：

    .. code-block:: python

        async def hook(
            *,
            state_values: State,
            thread_id: str,
            active_run: dict,
            dispatch_event: Callable[[BaseEvent], Any],
        ) -> AsyncGenerator[Any, None]: ...

    行为：
    - 无会话级 PV / ``resource_manager is None`` → 空 async generator（不 emit）
    - PaaS 调用异常 → ``logger.warning(exc_info=True)`` 后 return，不阻断主流程
    - 正常路径：调用 ``dispatch_event`` 触发 DB writer + SSE 分发，并 yield 结果

    :param resource_manager: 请求级 ResourceManager；``None`` 时 hook 直接退化
    :param executor_info: 传给 :class:`SandboxPvFileService` 的凭证信息
    """
    _executor_info = executor_info or {}

    async def hook(
        *,
        state_values: State,
        thread_id: str,
        active_run: dict,
        dispatch_event: DispatchEvent,
    ) -> AsyncGenerator[Any, None]:
        # 退化路径：无 PV 或无 resource_manager 时不 emit
        if not _has_session_pv(state_values) or resource_manager is None:
            return

        started_at = (active_run or {}).get("started_at")
        try:
            service = SandboxPvFileService(
                resource_manager=resource_manager,
                executor_info=_executor_info,
            )
            # list_files 是同步 HTTP + 分页 sleep，挪到线程池避免阻塞事件循环
            result = await asyncio.to_thread(
                service.list_files, session_code=thread_id, since=started_at
            )
            artifacts = _files_to_artifacts(result.get("results") or [])
        except Exception:
            logger.warning(
                "emit artifacts_generated failed: session=%s", thread_id, exc_info=True
            )
            return

        run_id = (active_run or {}).get("id", "")
        payload = {
            "runId": run_id,
            "status": "complete" if artifacts else "empty",
            "artifacts": artifacts,
        }
        logger.info(
            "artifacts_generated: session=%s run=%s count=%d",
            thread_id, run_id, len(artifacts),
        )
        yield dispatch_event(
            CustomEvent(
                type=EventType.CUSTOM,
                name=SessionPersistenceEventNames.ArtifactsGenerated.value,
                value=payload,
            )
        )

    return hook
