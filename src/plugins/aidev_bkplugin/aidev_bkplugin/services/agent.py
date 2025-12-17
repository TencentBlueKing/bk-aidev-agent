import base64
import json

from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.enums import AgentBuildType
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.chat import ChatCompletionAgent
from aidev_agent.services.pydantic_models import ChatPrompt, ExecuteKwargs
from django.conf import settings
from django.core.cache import cache
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .factory import agent_config_factory, agent_factory


def build_chat_completion_agent_by_session_code(session_code: str) -> ChatCompletionAgent:
    agent_cls = agent_factory.get(settings.DEFAULT_NAME)
    config_manager = agent_config_factory.get(settings.DEFAULT_NAME)
    return AgentInstanceFactory.build_agent(
        build_type=AgentBuildType.SESSION,
        session_code=session_code,
        agent_cls=agent_cls,
        config_manager_class=config_manager,
    )


def build_chat_completion_agent_by_chat_history(chat_history: list[ChatPrompt]) -> ChatCompletionAgent:
    role_contents = get_agent_role_info()
    if role_contents:
        chat_history = role_contents + chat_history
    agent_cls = agent_factory.get(settings.DEFAULT_NAME)
    config_manager = agent_config_factory.get(settings.DEFAULT_NAME)
    agent_instance = AgentInstanceFactory.build_agent(
        build_type=AgentBuildType.DIRECT,
        session_context_data=[each.model_dump() for each in chat_history],
        agent_cls=agent_cls,
        config_manager_class=config_manager,
    )
    return agent_instance


def get_agent_config_info(username: str | None = None):
    agent_info_key = f"get_agent_config_info:{username or 'default'}"

    agent_info = cache.get(agent_info_key)
    if not agent_info:
        client = BKAidevApi.get_client()
        result = client.api.retrieve_agent_config(
            path_params={"agent_code": settings.APP_CODE}, headers={"X-BKAIDEV-USER": username}
        )
        agent_info = result["data"]
        otel_env_info = agent_info.pop("otel_info", None)
        if otel_env_info:
            agent_info["otel_info"] = json.loads(base64.b64decode(otel_env_info).decode())
        cache.set(agent_info_key, agent_info, settings.DEFAULT_CACHE_TIMEOUT)
    return agent_info


def get_agent_role_info() -> list[ChatPrompt]:
    agent_config_info = get_agent_config_info()
    agent_role_content = agent_config_info["prompt_setting"].get("content", [])
    if not agent_role_content:
        return []

    for each in agent_role_content:
        each["role"] = each["role"].replace("hidden-", "")
        if each["role"] == "pause":
            each["role"] = "assistant"

    return [ChatPrompt(role=each["role"], content=each["content"]) for each in agent_role_content]


def run_bkplugin_invoke(
    chat_history: list[dict], execute_kwargs: dict, input: str | None = None, username: str | None = None
):
    execute_kwargs = build_execute_kwargs(execute_kwargs, username)
    execute_kwargs.stream = False
    chat_history = (
        [ChatPrompt(role=each["role"], content=each["content"]) for each in chat_history] if chat_history else []
    )
    role_contents = get_agent_role_info()
    if role_contents:
        chat_history = role_contents + chat_history
    if input:
        if chat_history:
            chat_history.append(ChatPrompt(role="user", content=input))
        else:
            chat_history = [ChatPrompt(role="user", content=input)]
    chat_completion_agent = build_chat_completion_agent_by_chat_history(chat_history)
    return chat_completion_agent.execute(execute_kwargs)


def build_execute_kwargs(_execute_kwargs: dict, username: str | None = None) -> ExecuteKwargs:
    execute_kwargs = ExecuteKwargs.model_validate(_execute_kwargs)
    execute_kwargs.caller_bk_biz_env = execute_kwargs.caller_bk_biz_env or "domestic_biz"
    execute_kwargs.caller_bk_app_code = execute_kwargs.caller_bk_app_code or "bkaidev"
    execute_kwargs.executor = execute_kwargs.executor or username or "anonymous"
    execute_kwargs.caller_executor = execute_kwargs.caller_executor or username or "anonymous"
    execute_kwargs.caller_order_type = execute_kwargs.caller_order_type or "ai_chat"
    if not execute_kwargs.caller_trace_context:
        current_span = trace.get_current_span()
        if current_span is not None and current_span.get_span_context().is_valid:
            carrier: dict[str, str] = {}
            propagator = TraceContextTextMapPropagator()
            propagator.inject(carrier, context=trace.set_span_in_context(current_span))
            execute_kwargs.caller_trace_context = carrier
    return execute_kwargs
