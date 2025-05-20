# -*- coding: utf-8 -*-
from typing_extensions import Protocol


class ApiProtocol(Protocol):
    def get_client_by_request(self, request):
        raise NotImplementedError

    def get_client_by_username(self, username):
        raise NotImplementedError
