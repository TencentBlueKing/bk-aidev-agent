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

import logging
import uuid
from copy import copy
from typing import Annotated, Callable, TypedDict

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from aidev_agent.api.paas_client import Client
from aidev_agent.pydantic_models import ExecuteKwargs

logger = logging.getLogger(__name__)


class PVState(TypedDict):
    runtime_paas_sbx_pv: Annotated[list[dict], add_pv_info]


def _is_session_pv(pv: dict) -> bool:
    """判断是否为 session 级 paas-sbx-pv。"""
    return pv.get("type") == "paas-sbx-pv" and pv.get("mount_path") == "session"


def _pv_identity(pv: dict) -> tuple:
    """返回 PV reducer 的逻辑身份。"""
    if _is_session_pv(pv):
        return ("paas-sbx-pv", "session")
    return tuple(sorted(pv.items()))


def add_pv_info(existing: list[dict], new: list[dict]) -> list[dict]:
    """合并 PV 信息。

    session 级 paas-sbx-pv 按逻辑身份 upsert，确保 runtime/platform source 更新不会追加重复
    session PV；非 session PV 保留原有完整 dict 去重语义。
    """
    result = list(existing or [])
    index = {_pv_identity(item): idx for idx, item in enumerate(result)}
    for item in new or []:
        key = _pv_identity(item)
        if key in index:
            result[index[key]] = item
        else:
            index[key] = len(result)
            result.append(item)
    return result


def _try_writeback(resource_manager, session_code: str, pv: dict) -> dict:
    """尝试将 session PV ID 写回平台。

    写回成功时返回 source="platform" 的 PV dict；
    写回失败时返回原始 PV dict（source 不变），不阻断 PV 下发。
    """
    volume_id = pv.get("volume_id")
    if resource_manager is None or not volume_id:
        return pv
    try:
        resource_manager.update_chat_session_sandbox_pv_id(session_code, volume_id)
    except Exception:
        logger.warning("PV writeback failed: session_code=%s", session_code, exc_info=True)
        return pv
    updated_pv = copy(pv)
    updated_pv["source"] = "platform"
    return updated_pv


def make_pv_node(
    client: Client,
    app_code: str,
    resource_manager=None,
    *,
    enable_pv_by_paas_runtime: bool = True,
    enable_pv_by_subagent: bool = True,
) -> Callable[[dict, RunnableConfig], dict]:
    """构建 PV 节点。

    PV 节点在第一次 paas_sandbox tool_call 前惰性创建 Volume，写入 state。
    同一会话中所有 paas_sandbox runtime 共享同一个 PV（通过 thread_id 唯一性保证）。

    Args:
        client: PaaS API Client 实例。
        app_code: 应用编码。
        resource_manager: per-request resource manager，用于写回 chat-session sandbox PV ID。
        enable_pv_by_paas_runtime: 是否在检测到 paas_sandbox tool_call 时创建 PV，默认 True
        enable_pv_by_subagent: 是否在检测到 Agent/sendMessages tool_call 时复用或创建 PV，默认 True

    Returns:
        可用于 LangGraph node 的 callable，接受 (state, config) 参数
    """

    def pv_node(state: dict, config: RunnableConfig) -> dict:
        # 步骤 1：检查是否已有 session 级别的 PV
        existing_pv = state.get("runtime_paas_sbx_pv", [])
        existing_session_pv = next((pv for pv in existing_pv if _is_session_pv(pv)), None)
        configurable = config.get("configurable", {})
        thread_id = configurable.get("thread_id", "")
        execute_kwargs: ExecuteKwargs | None = configurable.get("execute_kwargs")
        session_code = getattr(execute_kwargs, "session_code", None) if execute_kwargs else None

        if existing_session_pv:
            if existing_session_pv.get("source") == "platform":
                return {}
            if session_code:
                retried_pv = _try_writeback(resource_manager, session_code, existing_session_pv)
                if retried_pv.get("source") == "platform":
                    return {"runtime_paas_sbx_pv": [retried_pv]}
            return {}

        # 步骤 2：检查最后一条消息是否包含 paas_sandbox 或 agent tool_call
        messages = state.get("messages", [])
        if not messages:
            return {}

        last_message = messages[-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return {}

        should_create_pv = False

        if enable_pv_by_paas_runtime and any(
            tc.get("args", {}).get("target_runtime", "").startswith("paas_sandbox") for tc in last_message.tool_calls
        ):
            should_create_pv = True

        if (
            enable_pv_by_subagent
            and not should_create_pv
            and any(tc.get("name") in ("Agent", "sendMessages") for tc in last_message.tool_calls)
        ):
            should_create_pv = True

        if not should_create_pv:
            return {}

        # 步骤 2.5：创建前读会话已绑定的卷，避免覆盖上传路径先写入的 PV
        if session_code and resource_manager is not None:
            session = resource_manager.retrieve_chat_session(session_code)
            if isinstance(session, dict):
                existing_volume_id = str(
                    ((session.get("session_property") or {}).get("sandbox_pv_id") or "")
                ).strip()
                if existing_volume_id:
                    return {
                        "runtime_paas_sbx_pv": [
                            {
                                "type": "paas-sbx-pv",
                                "volume_id": existing_volume_id,
                                "volume_name": "",
                                "mount_path": "session",
                                "source": "platform",
                            }
                        ]
                    }

        # 步骤 3：使用 thread_id 构造 volume_name（thread_id 始终存在，session_code 可选）
        volume_name = f"agent-pv-{thread_id}-{str(uuid.uuid4())[:8]}"

        # 步骤 4：调用 API 创建 Volume
        resp = client.create_agent_sandbox_volume.request(
            json={"name": volume_name},
            path_params={"app_code": app_code},
        )
        resp.raise_for_status()
        result = resp.json()

        # 蓝鲸 API 响应格式：{"code": 0, "message": "OK", "data": {"uuid": "...", ...}}
        # 也可能直接在顶层返回 {"uuid": "..."}，两种格式都要兼容
        # 注意：data 键可能存在但值为 null，需要用 or 兜底
        data = result.get("data") or result
        volume_id = data.get("uuid") if isinstance(data, dict) else None
        if not volume_id:
            logger.error("create_agent_sandbox_volume response missing uuid: %s", result)
            return {}

        # 步骤 5：构造 runtime PV，有 session_code 时尽力写回管理平台
        runtime_pv = {
            "type": "paas-sbx-pv",
            "volume_id": volume_id,
            "volume_name": volume_name,
            "mount_path": "session",
            "source": "runtime",
        }
        pv = _try_writeback(resource_manager, session_code, runtime_pv) if session_code else runtime_pv

        # 步骤 6：返回 PV 信息写入 state
        return {"runtime_paas_sbx_pv": [pv]}

    return pv_node
