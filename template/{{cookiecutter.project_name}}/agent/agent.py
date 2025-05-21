# Sample for rewrite CommonQAAgent
from aidev_agent.core.extend.agent.qa import CommonQAAgent


class CommonQAAgentExtend(CommonQAAgent):
    @classmethod
    def get_agent_executor(cls, *args, **kwargs):
        print("extend QA agent")
        return CommonQAAgent.get_agent_executor(*args, **kwargs)
