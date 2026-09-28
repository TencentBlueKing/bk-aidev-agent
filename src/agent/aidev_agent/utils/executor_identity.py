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
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from logging import getLogger

from langchain_core.tools import ToolException

from aidev_agent.utils.tracing import recording_span

try:
    import bkoauth
    from bkoauth.exceptions import TokenNotExist
except ImportError:
    bkoauth = None

    class TokenNotExist(Exception):
        """bkoauth 未安装时的占位异常，不会被抛出。"""


_logger = getLogger(__name__)


@dataclass(frozen=True)
class ApproverIdentity:
    """一次 tool call 对应审批卡的审批人。"""

    approved_by: str
    tool_call_id: str


_current_approver: ContextVar[ApproverIdentity | None] = ContextVar("aidev_approver_identity", default=None)


@contextmanager
def approver_identity_scope(identity: ApproverIdentity | None) -> Iterator[None]:
    """绑定本次工具调用的审批人身份；None 显式隔离外层工具身份。"""
    token = _current_approver.set(identity)
    try:
        yield
    finally:
        _current_approver.reset(token)


def approver_authorization(transport: str, tool_name: str) -> str | None:
    """发起下游调用前构造审批人凭证请求头值；当前调用未绑定审批人时返回 None。

    审批人凭证缺失时直接抛出，禁止回退到调用者身份。
    """
    identity = _current_approver.get()
    if identity is None:
        return None
    with recording_span(
        "approval.executor_identity",
        attributes={
            "tool.transport": transport,
            "tool.name": tool_name,
            "tool.call_id": identity.tool_call_id,
            "bk_username": identity.approved_by,
        },
    ):
        access_token = _get_access_token_by_user(identity.approved_by)
    _logger.info(
        "[ToolApproval] 使用审批人身份调用下游: transport=%s, tool=%s, tool_call_id=%s, approved_by=%s",
        transport,
        tool_name,
        identity.tool_call_id,
        identity.approved_by,
    )
    return json.dumps({"access_token": access_token})


def _get_access_token_by_user(username: str) -> str:
    unauthorized = ToolException(f"审批人 {username} 未授权当前智能体应用，请将其加入 Agent SaaS 并完成授权后重新发起")
    fn = getattr(bkoauth, "get_access_token_by_user", None) if bkoauth else None
    if fn is None:
        raise ToolException("bkoauth 不可用，无法获取审批人凭证")
    # 仅“无授权记录”视为审批人未授权；接口或网络异常原样抛出，避免误导为未授权
    try:
        token = fn(username)
    except TokenNotExist as error:
        _logger.error("[ToolApproval] 审批人无 access_token 记录: approved_by=%s", username)
        raise unauthorized from error
    access_token = getattr(token, "access_token", None) if token else None
    if not access_token:
        _logger.error("[ToolApproval] 审批人 access_token 为空: approved_by=%s", username)
        raise unauthorized
    return access_token
