"""Transport-independent personal-memory methods shared by Agent and private clients."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aidev_agent.api.constants import AUTHORIZATION_HEADER

if TYPE_CHECKING:
    from bkapi_client_core.client import BaseClient as Client


class MemoryResourceManagerMixin:
    def _memory_client(self, username: str) -> Client:
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Personal memory requires an authenticated username")
        if self.access_token and self.username != username:
            raise ValueError("A personal-memory access_token must be bound to the requested username")
        client = self.get_client()
        client.update_bkapi_authorization(
            bk_username=username, access_token=self.resolve_access_token(username) or None
        )
        return client

    @staticmethod
    def _memory_headers(headers: dict | None) -> dict:
        if any(key.lower() == AUTHORIZATION_HEADER.lower() for key in (headers or {})):
            raise ValueError("Personal-memory authorization must come from the resource manager")
        return {key: value for key, value in (headers or {}).items() if key.lower() != "x-bkaidev-user"}

    def memory_schemas(self, *, username: str, agent_code: str, **kwargs) -> dict:
        headers = self._memory_headers(kwargs.pop("headers", None))
        if not isinstance(agent_code, str) or not agent_code.strip():
            raise ValueError("Personal memory requires an agent code")
        return self._memory_client(username).api.memory_schemas(
            params={"agent_code": agent_code}, headers=headers, **kwargs
        )["data"]

    def memory_tool(self, payload: dict, *, username: str, **kwargs) -> dict:
        headers = self._memory_headers(kwargs.pop("headers", None))
        return self._memory_client(username).api.memory_tool(json=payload, headers=headers, **kwargs)["data"]

    def complete_memory_round(self, payload: dict, *, username: str, **kwargs) -> dict:
        headers = self._memory_headers(kwargs.pop("headers", None))
        return self._memory_client(username).api.complete_memory_round(json=payload, headers=headers, **kwargs)["data"]
