# -*- coding: utf-8 -*-
"""蓝鲸智能体 API 网关客户端。

遵循项目 bkapi_client_core 模式
- Client(BaseClient)：用 bind_property 声明 API 操作
- BkAgentApi：通过 get_client() 创建 Client 实例

所有请求默认通过 X-Bkapi-Authorization header 携带用户态 access_token。
"""

from __future__ import annotations

import logging

from bkapi_client_core.base import Operation
from bkapi_client_core.client import BaseClient
from bkapi_client_core.django_helper import _get_client_by_settings
from bkapi_client_core.property import bind_property

from aidev_agent.api.base import ApiProtocol
from aidev_agent.api.constants import APIGW_URL_FORMAT, TENANT_HEADER
from aidev_agent.api.utils import get_endpoint
from aidev_agent.config import settings

logger = logging.getLogger(__name__)


class Client(BaseClient):
    """蓝鲸智能体 API 网关客户端。

    通过 bind_property 声明 bp-{agent_code} 微应用的 API 操作。
    实例由 BkAgentApi.get_client() 创建，endpoint 为 bp-{agent_code}/prod。
    通过 X-Bkapi-Authorization header 进行用户态鉴权。

    API 操作(通过平台鉴权，用户态身份调用):
    - ping: 私有端点 健康检查，用于处理是否分发到远程服务
    - private_chat_completion: 私有端点 (private/agent/chat_completion/)
    API 操作(通过网关鉴权，允许使用应用态身份调用):
    - openapi_chat_completion: OpenAPI 端点 (openapi/agent/chat_completion/)
    - create_session: OpenAPI 端点, 创建 session, 用于 2.0.0 以前不支持智能体维护 session 的场景
    - save_session_content: OpenAPI 端点, 保存 session 内容, 用于 2.0.0 以前不支持智能体维护 session 的场景
    """

    ping = bind_property(
        Operation,
        name="ping",
        method="GET",
        path="/bk_plugin/private/agent/ping/",
    )

    private_chat_completion = bind_property(
        Operation,
        name="private_chat_completion",
        method="POST",
        path="/bk_plugin/private/agent/chat_completion/",
    )

    openapi_chat_completion = bind_property(
        Operation,
        name="openapi_chat_completion",
        method="POST",
        path="/bk_plugin/openapi/agent/chat_completion/",
    )

    create_session = bind_property(
        cls=Operation,
        name="create_session",
        method="POST",
        path="/bk_plugin/plugin_api/session/",
    )

    save_session_content = bind_property(
        Operation,
        name="save_session_content",
        method="POST",
        path="/bk_plugin/plugin_api/session_content/",
    )


class BkAgentApi(ApiProtocol):
    """蓝鲸智能体 API 网关协议。

    遵循 paas_client.py / bk_aidev.py 模式：
    - get_client() 创建 Client 实例
    - endpoint 随 agent_code 动态变化（bp-{agent_code}/prod）
    - 通过 X-Bkapi-Authorization header 注入用户态 access_token
    """

    @classmethod
    def get_client(
        cls,
        agent_code: str,
        app_code: str = settings.APP_CODE,
        app_secret: str = settings.SECRET_KEY,
        access_token: str = "",
        endpoint: str = "",
        validate_endpoint: bool = False,
        tenant_id: str = "",
        **kwargs,
    ) -> Client:
        """获取指定 agent_code 的 Client 实例。

        Args:
            agent_code: 子智能体 code，用于构建 bp-{agent_code} endpoint
            app_code: 应用编码（bk_app_code）
            app_secret: 应用密钥（bk_app_secret）
            access_token: 用户认证令牌，通过 X-Bkapi-Authorization header 注入
            endpoint: API 网关 endpoint；为空时自动通过 get_endpoint 构建
            validate_endpoint: 是否校验 endpoint；为 True 时，若 endpoint 是不含环境的
                默认平台 URL（如 ``http://host/bp-{agent_code}/``），则清空并由
                ``get_endpoint`` 自动补全环境阶段
            tenant_id: 租户 ID；非空时通过 X-Bk-Tenant-Id header 透传，由父智能体经 executor_info 传入
            **kwargs: 传递给 _get_client_by_settings 的额外参数

        Returns:
            Client 实例，已配置 endpoint 和认证信息
        """
        if validate_endpoint and endpoint:
            # 适配：默认情况下，平台提供的 url 不会添加环境
            # 若 endpoint 以不含 stage 的模板结尾，则清空让 get_endpoint 自动补全
            bare_suffix = APIGW_URL_FORMAT.format(api_name=f"bp-{agent_code}", stage="").rstrip("/")
            if endpoint.endswith(bare_suffix):
                endpoint = ""
        if not endpoint:
            endpoint = get_endpoint(api_name=f"bp-{agent_code}", stage="prod")
        client = _get_client_by_settings(
            Client,
            endpoint=endpoint,
            bk_app_code=app_code,
            bk_app_secret=app_secret,
            **kwargs,
        )
        # 通过 X-Bkapi-Authorization header 注入用户态 access_token
        if access_token:
            client.update_bkapi_authorization(
                access_token=access_token or None,
                # bk_username=bk_username or ""
            )
        if tenant_id:
            client.update_headers({TENANT_HEADER: tenant_id})
        return client
