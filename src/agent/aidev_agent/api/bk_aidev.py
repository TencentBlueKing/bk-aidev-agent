# -*- coding: utf-8 -*-

from bkapi_client_core.django_helper import _get_client_by_settings
from bkapi_client_core.django_helper import get_client_by_request as _get_client_by_request
from bkapi_client_core.django_helper import get_client_by_username as _get_client_by_username
from bkapi_client_core.utils import generic_type_partial as _partial

from aidev_agent.api.base import ApiProtocol
from aidev_agent.api.bkaidev_client.client import Client
from aidev_agent.api.domains import BKAIDEV_URL
from aidev_agent.config import settings


class BKAidevApi(ApiProtocol):
    @classmethod
    def get_client(cls, app_code=settings.APP_CODE, app_secret=settings.SECRET_KEY) -> Client:
        return _get_client_by_settings(Client, endpoint=BKAIDEV_URL, bk_app_code=app_code, bk_app_secret=app_secret)

    @classmethod
    def get_client_by_request(cls, request):
        return _partial(Client, _get_client_by_request)(request, endpoint=BKAIDEV_URL)

    @classmethod
    def get_client_by_username(cls, username):
        return _partial(Client, _get_client_by_username)(username, endpoint=BKAIDEV_URL)
