import base64
import hashlib
import json
import logging
import os
import uuid
from urllib.parse import urlparse

import pkg_resources
from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.enums import AgentBuildType, ChatContentStatus, PromptRole, StreamEventType
from aidev_agent.services.agent import AgentInstanceFactory, ChatCompletionAgent
from aidev_agent.services.event_handlers import AGUISessionWriter
from aidev_agent.services.pydantic_models import ChatPrompt, ExecuteKwargs
from bkapi_client_core.exceptions import HTTPResponseError
from django.conf import settings
from langgraph.checkpoint.memory import MemorySaver

# OpenTelemetry 是可选 extras（pip install aidev-bkplugin[opentelemetry]）。
# 未安装时 trace context 注入功能降级为 no-op，其余流程不受影响。
try:
    from opentelemetry import trace
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
except ImportError:
    trace = None
    TraceContextTextMapPropagator = None

from .factory import agent_config_factory, agent_factory
from ..constants import AGUI_PROTOCOL_VERSION
from ..utils import bkaidev_api_client

logger = logging.getLogger(__name__)


def _get_checkpointer():
    """获取 Checkpointer 单例实例（延迟导入避免循环依赖）"""
    memory_saver = MemorySaver()
    return memory_saver


def build_chat_completion_agent_by_session_code(
    session_code: str,
    username: str = "",
    version: str | None = None,
) -> ChatCompletionAgent:
    """构建 ChatCompletionAgent

    Args:
        session_code: 会话标识
        username: 用户名
        version: 主 agent 配置版本；为空走最新版

    Returns:
        ChatCompletionAgent 实例
    """
    agent_cls = agent_factory.get(settings.DEFAULT_NAME)
    config_manager = agent_config_factory.get(settings.DEFAULT_NAME)

    # 构建 event_handler（如果提供了 client）
    event_handler = AGUISessionWriter(session_code=session_code, client=bkaidev_api_client, username=username)

    agent_instance = AgentInstanceFactory.build_agent(
        build_type=AgentBuildType.SESSION,
        session_code=session_code,
        agent_cls=agent_cls,
        config_manager_class=config_manager,
        checkpointer=_get_checkpointer(),
        event_handler=event_handler,
        username=username,
        version=version,
    )

    return agent_instance


def build_chat_completion_agent_by_chat_history(
    chat_history: list[ChatPrompt], username: str = "", version: str | None = None
) -> ChatCompletionAgent:
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
        checkpointer=_get_checkpointer(),
        username=username,
        version=version,
    )
    return agent_instance


def get_agent_config_info(username: str | None = None, version: str | None = None):
    """读取 agent 配置；按 ``(username, version)`` 维度做缓存隔离。

    :param version: agent 配置版本；为空时不传给后端，由后端返回最新版本，
        与历史行为兼容；缓存 key 落到 ``:latest`` 以避免污染指定版本的缓存。
    """
    client = BKAidevApi.get_client()
    api_kwargs: dict = {
        "path_params": {"agent_code": settings.APP_CODE},
        "headers": {"X-BKAIDEV-USER": username},
    }
    if version:
        api_kwargs["params"] = {"version": version}
    result = client.api.retrieve_agent_config(**api_kwargs)
    agent_info = result["data"]
    otel_env_info = agent_info.pop("otel_info", None)
    if otel_env_info:
        agent_info["otel_info"] = json.loads(base64.b64decode(otel_env_info).decode())
    return agent_info


def build_session_detail_url(session_code: str, username: str | None = None) -> str:
    """
    从 agent 配置的 saas_url 拼接小鲸会话详情页 URL。
    """
    if not session_code:
        return ""
    try:
        agent_info = get_agent_config_info(username)
        saas_url = agent_info.get("saas_url", "")
        if not saas_url:
            logger.debug(f"[build_session_detail_url] agent 配置中无 saas_url, username={username}")
            return ""
        # 从 saas_url 提取域名：https://xxx.bkapps.woa.com/bk_plugin/... → https://xxx.bkapps.woa.com
        parsed = urlparse(saas_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        return f"{base_url}/chat-window/?session={session_code}"
    except Exception as e:
        logger.warning(f"[build_session_detail_url] 构建会话详情 URL 失败: session_code={session_code}, error={e}")
        return ""


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
    chat_completion_agent, _ = build_chat_completion_agent_by_thread_id_with_chat_history(
        thread_id=execute_kwargs.session_code or str(uuid.uuid4()),
        chat_history=chat_history,
        username=username,
        version=execute_kwargs.version,
    )
    return chat_completion_agent.execute(execute_kwargs)


def build_execute_kwargs(_execute_kwargs: dict, username: str | None = None) -> ExecuteKwargs:
    execute_kwargs = ExecuteKwargs.model_validate(_execute_kwargs)
    execute_kwargs.caller_bk_biz_env = execute_kwargs.caller_bk_biz_env or "domestic_biz"
    execute_kwargs.caller_bk_app_code = execute_kwargs.caller_bk_app_code or "bkaidev"
    execute_kwargs.executor = execute_kwargs.executor or username or "anonymous"
    execute_kwargs.caller_executor = execute_kwargs.caller_executor or username or "anonymous"
    execute_kwargs.caller_order_type = execute_kwargs.caller_order_type or "ai_chat"
    if not execute_kwargs.caller_trace_context and trace is not None:
        current_span = trace.get_current_span()
        if current_span is not None and current_span.get_span_context().is_valid:
            carrier: dict[str, str] = {}
            propagator = TraceContextTextMapPropagator()
            propagator.inject(carrier, context=trace.set_span_in_context(current_span))
            execute_kwargs.caller_trace_context = carrier
    return execute_kwargs


def run_chat_completion_with_thread_id(
    thread_id: str,
    input_text: str,
    username: str,
    execute_kwargs: ExecuteKwargs,
    save_content: bool = True,
):
    """
    通过 thread_id 统一执行 ChatCompletion 并自动处理会话保存。
    供 builtin view 与 wxbot 共用，避免 HTTP 自调用。
    """
    if not input_text:
        raise ValueError("input_text is required when using thread_id")

    agent_instance, session_code = build_chat_completion_agent_by_thread_id(
        thread_id=thread_id,
        input_text=input_text,
        username=username,
        save_content=save_content,
        version=execute_kwargs.version,
    )
    execute_kwargs.session_code = session_code
    result = execute_agent_with_save(agent_instance, execute_kwargs, session_code, username)
    return result, session_code


def get_agent_version():
    """获取所有以 aidev 开头的已安装包及其版本"""
    installed_packages = pkg_resources.working_set
    abilities = {package.key: package.version for package in installed_packages if package.key.startswith("aidev")}

    if settings.VERSION_PATH and os.path.isfile(settings.VERSION_PATH):
        with open(settings.VERSION_PATH, "r") as f:
            abilities["version"] = f.read().strip()
    return abilities


def generate_session_code(username: str, agent_code: str, thread_id: str) -> str:
    """
    根据 username, agent_code, thread_id 生成唯一的 session_code
    使用 MD5 hash 保证长度固定且唯一
    """
    raw_string = f"{username}:{agent_code}:{thread_id}"
    return hashlib.md5(raw_string.encode()).hexdigest()


def get_or_create_session_by_thread_id(username: str, thread_id: str, agent_code: str | None = None) -> str:
    """
    根据 thread_id 获取或创建会话

    Returns:
        session_code
    """
    agent_code = agent_code or settings.APP_CODE
    session_code = generate_session_code(username, agent_code, thread_id)

    client = BKAidevApi.get_client()

    try:
        result = client.api.retrieve_chat_session(
            path_params={"session_code": session_code}, headers={"X-BKAIDEV-USER": username}
        )
        if result.get("data"):
            return session_code
    except HTTPResponseError as e:
        logger.warning("Error retrieving chat session: %s", e)
        if e.response_status_code == 404:
            # 会话不存在，创建新会话
            client.api.create_chat_session(
                json={
                    "session_code": session_code,
                    "session_name": f"Thread-{thread_id[:8]}",  # 使用 thread_id 前8位作为名称
                    "protocol_version": AGUI_PROTOCOL_VERSION,
                },
                headers={"X-BKAIDEV-USER": username},
            )
            return session_code
        else:
            raise e


def save_session_content(
    session_code: str, role: str, content: str, username: str, extra: dict | None = None, status: str = "success"
) -> dict:
    """
    保存会话内容到 BKAidev
    """
    client = BKAidevApi.get_client()
    data = {"session_code": session_code, "role": role, "content": content, "status": status}
    if extra:
        data["extra"] = extra

    result = client.api.create_chat_session_content(json=data, headers={"X-BKAIDEV-USER": username})
    return result.get("data", {})


def save_ai_response(result: dict, session_code: str, username: str):
    """
    保存非流式 AI 回复
    """
    content = ""
    if "choices" in result and result["choices"]:
        delta = result["choices"][0].get("delta", {})
        content = delta.get("content", "")

    if content:
        save_session_content(session_code=session_code, role=PromptRole.AI.value, content=content, username=username)


def save_chat_history_to_session(session_code: str, chat_history: list[ChatPrompt], username: str):
    """按顺序将 chat_history 持久化到指定 session。"""
    for prompt in chat_history or []:
        save_session_content(
            session_code=session_code,
            role=prompt.role,
            content=prompt.content,
            username=username,
        )


def _build_session_agent_for_thread(
    session_code: str, username: str, version: str | None = None
) -> ChatCompletionAgent:
    agent_cls = agent_factory.get(settings.DEFAULT_NAME)
    config_manager = agent_config_factory.get(settings.DEFAULT_NAME)

    event_handler = (
        AGUISessionWriter(session_code=session_code, client=bkaidev_api_client, username=username)
        if bkaidev_api_client
        else None
    )

    return AgentInstanceFactory.build_agent(
        build_type=AgentBuildType.SESSION,
        session_code=session_code,
        agent_cls=agent_cls,
        config_manager_class=config_manager,
        checkpointer=_get_checkpointer(),
        event_handler=event_handler,
        username=username,
        version=version,
    )


def build_chat_completion_agent_by_thread_id(
    thread_id: str,
    input_text: str,
    username: str,
    agent_code: str | None = None,
    save_content: bool = True,
    version: str | None = None,
) -> tuple[ChatCompletionAgent, str]:
    """
    通过 thread_id 构建 Agent

    Args:
        thread_id: Thread ID
        input_text: 用户输入
        username: 用户名
        agent_code: 智能体代码
        save_content: 是否保存会话内容
        version: 主 agent 配置版本；为空走最新版

    Returns:
        tuple[agent_instance, session_code]
    """
    agent_code = agent_code or settings.APP_CODE

    # 1. 获取或创建会话
    session_code = get_or_create_session_by_thread_id(username, thread_id, agent_code)

    # 2. 保存用户输入到会话
    if save_content and input_text:
        save_session_content(session_code, PromptRole.USER.value, input_text, username)

    return _build_session_agent_for_thread(session_code, username, version=version), session_code


def build_chat_completion_agent_by_thread_id_with_chat_history(
    thread_id: str,
    chat_history: list[ChatPrompt],
    username: str,
    agent_code: str | None = None,
    version: str | None = None,
) -> tuple[ChatCompletionAgent, str]:
    """
    通过 thread_id 构建 Agent，并先将传入的 chat_history 写入对应 session。

    Args:
        thread_id: Thread ID
        chat_history: 会话历史
        username: 用户名
        agent_code: 智能体代码
        version: 主 agent 配置版本；为空走最新版

    Returns:
        tuple[agent_instance, session_code]
    """
    agent_code = agent_code or settings.APP_CODE
    session_code = get_or_create_session_by_thread_id(username, thread_id, agent_code)
    save_chat_history_to_session(session_code=session_code, chat_history=chat_history, username=username)
    return _build_session_agent_for_thread(session_code, username, version=version), session_code


def execute_agent_with_save(
    agent_instance: ChatCompletionAgent,
    execute_kwargs,
    session_code: str,
    username: str,
):
    """
    执行 Agent 并自动保存 AI 回复

    Args:
        agent_instance: Agent 实例
        execute_kwargs: 执行参数
        session_code: 会话代码
        username: 用户名

    Returns:
        流式模式返回生成器，非流式模式返回结果字典
    """
    if execute_kwargs.stream:
        generator = agent_instance.execute(execute_kwargs)
        return wrap_generator_with_save(generator, session_code, username)
    else:
        result = agent_instance.execute(execute_kwargs)
        save_ai_response(result, session_code, username)
        return result


def wrap_generator_with_save(generator, session_code: str, username: str):
    """
    包装流式生成器，在完成后保存 AI 回复

    SSE 数据格式说明：
    - event=think: 思考过程
    - event=text: 实际回复内容
    - event=error: 错误信息，错误信息在message字段
    - event=reference_doc: 知识库引用文档
    """

    message_parts = []  # 按顺序保存消息片段，每个元素为 (event_type, content)
    current_event_type = None
    current_content = []
    has_error = False  # 标记是否有错误发生

    def _flush_current_content():
        """将当前收集的内容刷新到 message_parts"""
        nonlocal current_event_type, current_content
        if current_event_type and current_content:
            message_parts.append((current_event_type, "".join(current_content)))
        current_content = []

    try:
        for chunk in generator:
            yield chunk
            # 解析 SSE 格式收集内容
            if chunk.startswith("data: ") and chunk.strip() != "data: [DONE]":
                try:
                    data = json.loads(chunk[6:])
                    event_type = data.get("event", "")
                    content = data.get("content", "")
                    cover = data.get("cover", "")

                    if cover:
                        message_parts = []
                        current_content = []  # 同时清空当前正在收集的内容

                    # 事件类型变更时，先保存之前的内容
                    if event_type != current_event_type:
                        _flush_current_content()
                        current_event_type = event_type

                    if (
                        event_type == StreamEventType.THINK.value
                        and content
                        or event_type == StreamEventType.TEXT.value
                        and content
                    ):
                        current_content.append(content)
                    elif event_type == StreamEventType.ERROR.value:
                        content = data.get("message")
                        current_content.append(content)
                        has_error = True  # 标记有错误发生
                    elif event_type == StreamEventType.REFERENCE_DOC.value:
                        docs = data.get("documents", [])
                        if isinstance(docs, list) and docs:
                            message_parts.append((StreamEventType.REFERENCE_DOC.value, docs))
                except json.JSONDecodeError:
                    logger.info(f"JSON解析失败: {chunk}")

    finally:
        # 刷新最后一批内容
        _flush_current_content()

        final_content_parts = []

        # 事件类型到格式化函数的映射
        handlers = {
            StreamEventType.THINK.value: format_think_content,
            StreamEventType.TEXT.value: lambda x: x,
            StreamEventType.ERROR.value: lambda x: x,
            StreamEventType.REFERENCE_DOC.value: format_reference_docs,
        }

        for event_type, content in message_parts:
            handler = handlers.get(event_type)
            if handler and content:
                final_content_parts.append(handler(content))

        if final_content_parts:
            save_session_content(
                session_code=session_code,
                role=PromptRole.AI.value,
                content="".join(final_content_parts),
                username=username,
                status=ChatContentStatus.ERROR.value if has_error else ChatContentStatus.SUCCESS.value,
            )


def format_think_content(content: str) -> str:
    """格式化思考内容为 HTML 样式"""
    return (
        f'<section class="think-head click-close closed">'
        f'<i class="ai-ui-sdk-icon ai-ui-sdk-sikao"></i>已完成思考'
        f'<i class="ai-ui-sdk-icon ai-ui-sdk-angle-up"></i>'
        f"</section>"
        f'<section class="think-body">{content}</section>'
    )


def format_reference_docs(documents: list) -> str:
    """格式化知识库引用文档为 HTML 样式"""
    if not documents:
        return ""

    html_content = (
        f'<section class="knowledge-head click-close">'
        f'<svg class="ai-ui-sdk-wenzhang"><use href="#ai-ui-sdk-wenzhang"></use></svg>'
        f"找到 {len(documents)} 篇资料参考"
        f'<i class="ai-ui-sdk-icon ai-ui-sdk-angle-up"></i>'
        f'</section><ul class="knowledge-body">'
    )

    for doc in documents:
        metadata = doc.get("metadata", {}) if isinstance(doc, dict) else {}
        path = metadata.get("path", "")
        file_path = metadata.get("file_path", "")
        display_name = metadata.get("display_name", "")
        preview_path = metadata.get("preview_path", "")

        title = display_name or (file_path.split("/")[-1] if file_path else "")
        text_path = preview_path or path

        html_content += (
            f'<li class="knowledge-item">'
            f'<i class="ai-ui-sdk-icon ai-ui-sdk-zhishiku"></i>'
            f'<a href="{text_path}" title="{title} ({text_path})" target="_blank" '
            f'class="knowledge-link g-flex-truncate">{title}</a>'
            f'<a href="{path}" title="预览原文" target="_blank" class="knowledge-link hover-show">'
            f'<i class="ai-ui-sdk-icon ai-ui-sdk-yanjing-kejian"></i></a>'
            f"</li>"
        )

    html_content += "</ul>"
    return html_content
