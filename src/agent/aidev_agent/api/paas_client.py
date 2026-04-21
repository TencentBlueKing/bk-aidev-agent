# -*- coding: utf-8 -*-
from bkapi_client_core.base import Operation
from bkapi_client_core.client import BaseClient
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

    delete_file = bind_property(
        Operation,
        name="delete_file",
        method="DELETE",
        path="agent_sandbox/sandboxes/{sandbox_id}/files/",
    )


class BkPaaSSandboxApi:
    _api_name = "paasv3" if settings.RUN_VER == "ieod" else "bkpaas3"

    @classmethod
    def get_client_by_request(cls, request):
        return _partial(Client, _get_client_by_request)(request, endpoint=get_endpoint(cls._api_name, stage="prod"))

    @classmethod
    def get_client_by_username(cls, username):
        return _partial(Client, _get_client_by_username)(username, endpoint=get_endpoint(cls._api_name, stage="prod"))
