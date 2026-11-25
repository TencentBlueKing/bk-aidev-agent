"""BKAI_CHAT_USE_CELERY=0 时的 Chat 执行：在当前 Web 进程内构建并执行 Agent，不投递 Celery。"""

from django.conf import settings

from .agent_builder import AgentBuilder, LLMOverrideResourceManager
from .agent_execution import AgentExecutor
from .producer_dispatch import ChatExecutionSpec


class ChatInlineDispatcher:
    """与 ChatDispatcher 保持相同的 execute 接口，便于视图层按配置切换。"""

    def __init__(self, spec: ChatExecutionSpec):
        self.spec = spec

    def execute(self, execute_kwargs):
        spec = self.spec
        factory = getattr(settings, "BKAI_CHAT_RESOURCE_MANAGER_FACTORY", LLMOverrideResourceManager)
        builder = AgentBuilder(
            username=spec.username,
            agent_code=spec.agent_code,
            resource_manager=factory(username=spec.username, model=spec.model, tenant_id=spec.tenant_id),
            turn_id=spec.turn_id,
            model=spec.model,
            temperature=spec.temperature,
            retry_strategy=spec.retry_strategy,
            reasoning_effort=spec.reasoning_effort,
        )
        agent = builder.by_session_code(spec.session_code, version=spec.version, channel_type=spec.channel_type)
        if not execute_kwargs.input and not agent.chat_history:
            raise ValueError("The chat history cannot be empty. Please provide input.")
        output = AgentExecutor(builder.session_manager).execute_with_save(
            agent, execute_kwargs, spec.session_code, turn_id=spec.turn_id
        )
        event_handler = getattr(agent, "event_handler", None)
        if execute_kwargs.stream and event_handler and hasattr(event_handler, "set_streaming_started"):
            event_handler.set_streaming_started()
        return output