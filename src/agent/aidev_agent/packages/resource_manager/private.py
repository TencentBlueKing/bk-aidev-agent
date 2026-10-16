"""Per-user OAuth ResourceManager for CLI personal-memory integration."""

from aidev_agent.api.private import PrivateMemoryClient

from .memory import MemoryResourceManagerMixin


class PrivateResourceManager(MemoryResourceManagerMixin):
    """Implements the memory boundary only; unrelated resources use host adapters.

    Create one instance per authenticated user and selected, registered Agent.
    endpoint is the APIGW stage URL. No application secret or Django OAuth lookup.
    """

    def __init__(self, *, endpoint: str, access_token: str, username: str, agent_code: str):
        values = {"endpoint": endpoint, "access_token": access_token, "username": username, "agent_code": agent_code}
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise ValueError("Private memory requires endpoint, access_token, authenticated username and agent_code")
        self.endpoint = endpoint
        self.access_token = access_token
        self.username = username
        self.agent_code = agent_code

    def get_agent_code(self, **kwargs):
        return self.agent_code

    def get_client(self):
        client = PrivateMemoryClient(endpoint=self.endpoint)
        client.update_bkapi_authorization(access_token=self.access_token)
        return client

    def _memory_client(self, username):
        if username != self.username:
            raise ValueError("Private memory is bound to its authenticated username")
        return self.get_client()

    def _check_agent(self, code):
        if code != self.agent_code:
            raise ValueError("Private memory is bound to its selected agent_code")

    def memory_schemas(self, *, username, agent_code, **kwargs):
        self._check_agent(agent_code)
        return super().memory_schemas(username=username, agent_code=agent_code, **kwargs)

    def memory_tool(self, payload, *, username, **kwargs):
        self._check_agent(payload.get("agent_code"))
        return super().memory_tool(payload, username=username, **kwargs)

    def complete_memory_round(self, payload, *, username, **kwargs):
        self._check_agent(payload.get("agent_code"))
        return super().complete_memory_round(payload, username=username, **kwargs)
