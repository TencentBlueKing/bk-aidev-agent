from django.apps import AppConfig


class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "agent"

    def ready(self) -> None:
        # register your extension here
        from bk_plugin.factory import agent_factory
        from bk_plugin.meta import DEFAULT_AGENT

        from agent.agent import CommonQAAgentExtend

        agent_factory.register(DEFAULT_AGENT, CommonQAAgentExtend)
        return super().ready()
