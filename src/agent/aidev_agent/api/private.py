"""User OAuth endpoints; never fall back to application/runtime routes."""

from bkapi_client_core.base import Operation, OperationGroup
from bkapi_client_core.client import BaseClient
from bkapi_client_core.property import bind_property


class PrivateMemoryApiGroup(OperationGroup):
    memory_schemas = bind_property(
        Operation, name="memory_schemas", method="GET", path="/openapi/aidev/private/v1/memory/schemas/"
    )
    memory_tool = bind_property(
        Operation, name="memory_tool", method="POST", path="/openapi/aidev/private/v1/memory/tool/"
    )
    complete_memory_round = bind_property(
        Operation, name="complete_memory_round", method="POST", path="/openapi/aidev/private/v1/memory/complete_round/"
    )


class PrivateMemoryClient(BaseClient):
    api = bind_property(PrivateMemoryApiGroup, name="api")
