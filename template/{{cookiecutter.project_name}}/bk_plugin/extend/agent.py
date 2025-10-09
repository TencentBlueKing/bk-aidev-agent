from aidev_agent.core.extend.agent.qa import CommonQAAgent


class CommonQAAgentExtend(CommonQAAgent):
    # extend your agent here

    @classmethod
    def get_agent_executor(cls, *args, **kwargs):
        # you can add extra tools here

        return CommonQAAgent.get_agent_executor(*args, **kwargs)
