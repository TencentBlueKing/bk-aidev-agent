import pytest
from aidev_agent.services.agent import memory


@pytest.fixture(autouse=True)
def isolated_memory_policy_cache():
    memory._policy_suppressed_until.clear()
    yield
    memory._policy_suppressed_until.clear()
