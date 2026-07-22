# -*- coding: utf-8 -*-
from bkapi_client_core.base import Operation
from bkapi_client_core.client import BaseClient
from bkapi_client_core.django_helper import _get_client_by_settings
from bkapi_client_core.django_helper import get_client_by_request as _get_client_by_request
from bkapi_client_core.django_helper import get_client_by_username as _get_client_by_username
from bkapi_client_core.property import bind_property
from bkapi_client_core.utils import generic_type_partial as _partial

from aidev_agent.api.utils import get_endpoint
from aidev_agent.config import settings


class Client(BaseClient):
    create_sandbox = bind_property(
        Operation,
        name="create_sandbox",
        method="POST",
        path="agent_sandbox/applications/{app_code}/sandboxes/",
    )

    delete_sandbox = bind_property(
        Operation,
        name="delete_sandbox",
        method="DELETE",
        path="agent_sandbox/sandboxes/{sandbox_id}/",
    )

    exec_command = bind_property(
        Operation,
        name="exec_command",
        method="POST",
        path="agent_sandbox/sandboxes/{sandbox_id}/processes/exec",
    )

    upload_file = bind_property(
        Operation,
        name="upload_file",
        method="POST",
        path="agent_sandbox/sandboxes/{sandbox_id}/files/upload",
    )

    download_file = bind_property(
        Operation,
        name="download_file",
        method="GET",
        path="agent_sandbox/sandboxes/{sandbox_id}/files/download",
    )

    list_agent_sandbox_volumes = bind_property(
        Operation,
        name="list_agent_sandbox_volumes",
        method="GET",
        path="agent_sandbox/applications/{app_code}/volumes/",
    )

    create_agent_sandbox_volume = bind_property(
        Operation,
        name="create_agent_sandbox_volume",
        method="POST",
        path="agent_sandbox/applications/{app_code}/volumes/",
    )

    delete_agent_sandbox_volume = bind_property(
        Operation,
        name="delete_agent_sandbox_volume",
        method="DELETE",
        path="agent_sandbox/applications/{app_code}/volumes/{volume_id}",
    )

    list_files = bind_property(
        Operation,
        name="list_files",
        method="GET",
        path="agent_sandbox/applications/{app_code}/volumes/{volume_id}/files",
    )

    delete_file = bind_property(
        Operation,
        name="delete_file",
        method="DELETE",
        path="agent_sandbox/applications/{app_code}/volumes/{volume_id}/files",
    )

    stat_file = bind_property(
        Operation,
        name="stat_file",
        method="GET",
        path="agent_sandbox/applications/{app_code}/volumes/{volume_id}/files/stat",
    )

    preview_file = bind_property(
        Operation,
        name="preview_file",
        method="GET",
        path="agent_sandbox/applications/{app_code}/volumes/{volume_id}/files/preview",
    )

    get_download_url = bind_property(
        Operation,
        name="get_download_url",
        method="GET",
        path="agent_sandbox/applications/{app_code}/volumes/{volume_id}/files/download_url",
    )


class BkPaaSSandboxApi:
    _api_name = "paasv3" if settings.RUN_VER == "ieod" else "bkpaas3"

    @classmethod
    def get_client(cls, app_code=None, app_secret=None, **kwargs):
        """使用显式 app_code/app_secret 创建 Client（应用态认证）。

        当运行在 gongfeng 等平台进程时，Django settings 的 BK_APP_CODE 是平台的凭证，
        而非 Agent 应用的凭证。通过此方法可显式传入正确的 app_code/app_secret，
        避免 PaaS Sandbox API 因 bk_app_code 与 URL 路径不匹配而拒绝请求。
        """
        return _get_client_by_settings(
            Client,
            endpoint=get_endpoint(cls._api_name, stage="prod"),
            bk_app_code=app_code,
            bk_app_secret=app_secret,
            **kwargs,
        )

    @classmethod
    def get_client_by_request(cls, request):
        return _partial(Client, _get_client_by_request)(request, endpoint=get_endpoint(cls._api_name, stage="prod"))

    @classmethod
    def get_client_by_username(cls, username, app_code=None, app_secret=None, **kwargs):
        return _partial(Client, _get_client_by_username)(
            username,
            endpoint=get_endpoint(cls._api_name, stage="prod"),
            bk_app_code=app_code,
            bk_app_secret=app_secret,
            **kwargs,
        )
