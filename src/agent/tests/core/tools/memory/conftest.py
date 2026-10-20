from unittest.mock import MagicMock

import pytest
from aidev_agent.core.tools.memory import PersonalMemoryRuntime


@pytest.fixture
def runtime():
    manager = MagicMock()
    manager.memory_schemas.return_value = [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": "Test memory tool",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        }
        for name in ["memory_write", "memory_update", "memory_search"]
    ]
    manager.memory_schemas.return_value = {
        "enabled": True,
        "agent_code": "agent-a",
        "memory_epoch": 1,
        "enabled_at": None,
        "schemas": manager.memory_schemas.return_value,
    }
    manager.memory_tool.return_value = {
        "hits": [{"memory_id": "used", "text": "Use Python"}, {"memory_id": "unused", "text": "Prefer tea"}]
    }
    return PersonalMemoryRuntime(
        lambda config: {
            "username": "alice",
            "agent_code": "agent-a",
            "session_id": "session-1",
            "session_date": "2026-10-09",
            "messages": [],
        },
        manager=manager,
        reference_model=MagicMock(),
    )
