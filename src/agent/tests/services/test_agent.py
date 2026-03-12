import pytest
from aidev_agent.config import settings
from aidev_agent.services.agent import AgentInstanceFactory


@pytest.mark.skipif(
    not all([settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
@pytest.mark.slow
class TestAgentFactorBuilder:
    def test_build_agent_from_session(self):
        session_code = "test"
        agent = AgentInstanceFactory.build_agent(session_code=session_code)
        assert agent is not None
