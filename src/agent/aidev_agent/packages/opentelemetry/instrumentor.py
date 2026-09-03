# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import logging
from typing import Any, Collection, Dict, Optional

import orjson
from langchain_core.messages import BaseMessage
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from wrapt import wrap_function_wrapper

from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.utils.tracing import set_agent_tracer

from .callback_handler import BkAidevAgentCallbackHandler, BkAidevAgentInjector
from .config import OTelConfig
from .metrics import configure_metrics
from .otel_service import BkAgentOTelService
from .utils import dont_throw

logger = logging.getLogger(__name__)

_instruments = ("langchain-core > 0.1.0",)


class BkAidevAgentInstrumentor(BaseInstrumentor):
    """
    BkAidevAgentInstrumentor 对于 AidevAgent 进行了插桩
    为了避免由于全局设置的采样等原因导致公共数据收集不全
    默认使用由 BkAidevAgentInstrumentor 提供的 tracer_provider 而不是全局的 tracer_provider
    将在 instrument 的时候，启动 otel_service
    请注意，不要使用 BkAidevAgentInstrumentor().instrument() 多次，由于 BaseInstrumentor() 是单例化的，第二次会导致 trace 获取异常

    设计说明（线程归属）：
        历史方案曾在 ``ChatCompletionAgent._execute`` 上注入，由 ``_wrap_generator``
        在迭代结束时触发 ``BkAidevAgentInjector.on_bk_agent_end``。问题：在流式场景下
        生成器的实际驱动发生在 ``streaming_helper`` 的 producer 线程中，而注入器
        的 end 触发点却挂在 HTTP 请求线程上（消费者侧）。当用户关闭页面、gunicorn
        kill 掉 HTTP 线程时，``on_bk_agent_end`` 永远不会被调用，root span 无法
        上报。
        现方案：取消 ``_execute`` 的 wrap。``BkAidevAgentCallbackHandler`` 持有
        injector，在 LangChain 顶层 chain 的 ``on_chain_end`` / ``on_chain_error``
        中结束 root span —— 这些 callback 由 LangChain 在真正驱动 Runnable 的线程上
        触发（流式场景下即 producer 线程），不再受 HTTP 线程存活的影响。
    """

    def __init__(self, config: OTelConfig):
        """初始化插桩器。

        Args:
            config: 必须显式提供 ``OTelConfig``。本插桩器内部读取
                ``config.enabled`` / ``config.enable_traces`` / ``config.debug`` /
                ``config.max_input_attribute_length`` / ``config.max_output_attribute_length`` 等字段；若放任为
                ``None`` 会在
                ``_get_agent`` wrap 中触发 ``AttributeError``，因此在构造期强制要求。
        """
        if config is None:
            raise TypeError("BkAidevAgentInstrumentor requires a non-None OTelConfig")
        self._otel_service_config = config
        configure_metrics(config.enabled and config.enable_metrics)
        self._otel_service: Optional[BkAgentOTelService] = None

    def start_otel_service(self):
        if self._otel_service is None:
            self._otel_service = BkAgentOTelService(self._otel_service_config)
            self._otel_service.start()

    def stop_otel_service(self):
        if self._otel_service is not None:
            self._otel_service.stop()

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, tracer=None, **kwargs):
        if tracer is None:
            self.start_otel_service()
            tracer = self._otel_service.get_tracer(__name__)
        set_agent_tracer(tracer)
        # 在 _get_agent 阶段一次性完成：
        #   1. 创建 root span（HTTP 线程，便于同步 RPC 关联）
        #   2. 注入 caller_trace_context 用于跨服务传播
        #   3. 构造 BkAidevAgentCallbackHandler，并把 injector 交给它
        #      (callback handler 在顶层 chain end/error 时收尾 root span)
        wrap_function_wrapper(
            module="aidev_agent.services.agent.chat",
            name="ChatCompletionAgent._get_agent",
            wrapper=ChatCompletionAgentGetAgentWrapper(tracer, self._otel_service_config),
        )
        # 注入知识库检索节点的可观测性
        wrap_function_wrapper(
            module="aidev_agent.core.nodes.knowledge",
            name="AgentKnowledgeNode.__call__",
            wrapper=AgentKnowledgeNodeCallWrapper(),
        )

    def _uninstrument(self, **kwargs):
        """
        取消自动插桩

        恢复 langchain_core.callbacks.BaseCallbackManager.__init__
        的原始实现。

        Returns:
            bool: 是否成功取消插桩
        """
        self.stop_otel_service()
        set_agent_tracer(None)
        unwrap("aidev_agent.services.agent.chat", "ChatCompletionAgent._get_agent")
        unwrap("aidev_agent.core.nodes.knowledge", "AgentKnowledgeNode.__call__")


def _get_trace_cb_from_callbacks(callbacks):
    if callbacks is None:
        return None
    if isinstance(callbacks, (list, tuple)):
        callbacks_list = callbacks
    elif hasattr(callbacks, "handlers"):
        # CallbackManager / AsyncCallbackManager
        callbacks_list = callbacks.handlers
    else:
        callbacks_list = [callbacks]
    for cb in callbacks_list:
        if isinstance(cb, BkAidevAgentCallbackHandler):
            return cb
    return None


class AgentKnowledgeNodeCallWrapper:
    """
    AgentKnowledgeNode.__call__ 的可观测性包装器

    为 AgentKnowledgeNode 的知识库检索添加 OpenTelemetry 追踪，
    功能与 IntentRecognitionMixinIntentRecognition 类似。
    """

    def _get_trace_cb_from_config(self, config):
        """从 RunnableConfig 中获取 BkAidevAgentCallbackHandler"""
        if config is None:
            return None
        callbacks = config.get("callbacks")
        return _get_trace_cb_from_callbacks(callbacks)

    def _get_query_from_state(self, state):
        """从 state 中获取查询文本，优先级: query > input > messages[-1].content"""
        query = state.get("query")
        if query is None:
            query = state.get("input")
        if query is None:
            messages = state.get("messages")
            if messages:
                query = messages[-1].content
        return query or ""

    def get_attributes(self, state, config, instance) -> Dict[str, Any]:
        """获取 span 属性"""
        query = self._get_query_from_state(state)
        attributes: Dict[str, Any] = {"rag.query": query}

        agent_options = getattr(instance, "agent_options", None)
        if agent_options is not None:
            kb_options = agent_options.knowledge_query_options
            if kb_options is not None:
                attributes.update(
                    {
                        "rag.knowledge_bases": [kb.get("id") for kb in kb_options.knowledge_bases],
                        "rag.knowledge_items": [ki.get("id") for ki in kb_options.knowledge_items],
                    }
                )
                if hasattr(kb_options, "model_dump"):
                    attributes["rag.kb_options"] = orjson.dumps(kb_options.model_dump(mode="json"))
        return attributes

    def get_id_by_docs(self, docs):
        """从文档列表中提取 ID"""
        if isinstance(docs, list):
            return [i.get("id") for i in docs]
        return []

    @dont_throw
    def _on_end(self, span, ret):
        """在 span 结束时设置召回结果属性"""
        if ret.get("knowledge_resources_emb_recalled"):
            span.set_attribute(
                "rag.knowledge_resources_emb_recalled",
                orjson.dumps(self.get_id_by_docs(ret.get("knowledge_resources_emb_recalled"))),
            )
        if ret.get("knowledge_resources_highly_relevant"):
            span.set_attribute(
                "rag.knowledge_resources_highly_relevant",
                orjson.dumps(self.get_id_by_docs(ret.get("knowledge_resources_highly_relevant"))),
            )
        if ret.get("knowledge_resources_moderately_relevant"):
            span.set_attribute(
                "rag.knowledge_resources_moderately_relevant",
                orjson.dumps(self.get_id_by_docs(ret.get("knowledge_resources_moderately_relevant"))),
            )

    def __call__(self, wrapped, instance, args, kwargs):
        """
        包装 AgentKnowledgeNode.__call__ 方法

        方法签名: __call__(self, state, config, *, store)
        """
        # 解析参数
        state = args[0] if args else kwargs.get("state")
        config = args[1] if len(args) > 1 else kwargs.get("config")

        trace_cb = self._get_trace_cb_from_config(config)

        if trace_cb is not None:
            attributes = self.get_attributes(state, config, instance)
            with trace_cb.create_custom_span("rag.retrieval", attributes=attributes) as span:
                ret = wrapped(*args, **kwargs)
                self._on_end(span, ret)
        else:
            ret = wrapped(*args, **kwargs)
        return ret


class ChatCompletionAgentGetAgentWrapper:
    """包装 ``ChatCompletionAgent._get_agent``。

    职责（按发生顺序）：

    1. 提取 ``messages`` / ``execute_kwargs`` / ``agent_info``，作为 root span start
       入参的快照——但**不立即创建 root span**；
    2. 创建 ``BkAidevAgentInjector`` 实例（持有 tracer / parent_trace_context / debug
       配置），但延迟 ``on_bk_agent_start`` 的触发；
    3. 执行原始 ``_get_agent`` 拿到 graph + cfg；该函数自身失败直接抛出，不会有
       ``agent.execution`` span 残留（图都没构造出来本来就不该有）；
    4. 构造 ``BkAidevAgentCallbackHandler`` 并把 injector + start 入参快照都交给它，
       挂入 ``cfg.callbacks``。

    线程归属（关键设计）：

    root span 的 **start 与 end 都由 callback handler 在执行线程上触发**：
    - 顶层 ``on_chain_start`` 首次触发时调用 ``injector.on_bk_agent_start``
    - 顶层 ``on_chain_end`` / ``on_chain_error`` 时调用 ``injector.on_bk_agent_end``

    流式场景下"执行线程 = producer 线程"，HTTP 请求线程被 gunicorn kill 不影响 trace
    上报；非流式场景下"执行线程 = HTTP 线程"，行为与之前一致。``debug.thread_id`` /
    ``debug.end_thread_id`` 因此始终一致，不再跨线程。
    """

    def __init__(self, tracer, config: OTelConfig):
        """
        初始化包装器
        """
        self.tracer = tracer
        self.config = config

    @staticmethod
    def _extract_user_input(messages) -> Any:
        """从 messages 末尾提取用户输入文本，用于 root span 的 ``agent.session.input``"""
        if isinstance(messages, list) and len(messages) >= 1 and isinstance(messages[-1], BaseMessage):
            return messages[-1].content
        logger.warning("用户调用 Agent 时未传入有效 messages，user_input 为 None")
        return None

    @staticmethod
    def _extract_agent_info(instance) -> Dict[str, Any]:
        """提取 agent_info 并剔除 otel_info（避免污染 span 属性）"""
        agent_info = dict(instance.agent_info) if instance and instance.agent_info else {}
        agent_info.pop("otel_info", None)
        return agent_info

    def __call__(
        self,
        wrapped,
        instance,
        args,
        kwargs,
    ):
        # 提取构造 root span 所需的入参快照（延迟到执行线程的 on_chain_start 顶层触发时使用）
        messages = args[0] if args else kwargs.get("messages", [])
        execute_kwargs = kwargs.get("execute_kwargs") or ExecuteKwargs()
        agent_info = self._extract_agent_info(instance)
        user_input = self._extract_user_input(messages)

        # 仅创建 injector 实例，不立即 on_bk_agent_start。
        # parent_trace_context 取自上游 caller（HTTP header 解出的 traceparent，由 view
        # 层在 build_execute_kwargs 中写入）；root span 创建后将以此为父。
        injector = BkAidevAgentInjector(
            tracer=self.tracer,
            parent_trace_context=execute_kwargs.caller_trace_context,
            debug=self.config.debug,
        )

        # _get_agent 自身失败直接抛出：图都没构造出来，也不应该有 agent.execution span。
        agent, cfg = wrapped(*args, **kwargs)

        # 构造 callback handler，把 injector + start 入参快照都交给它。
        # root span 的 start/end 都由 callback handler 在执行线程上触发。
        callbacks = cfg.setdefault("callbacks", [])
        callback_handler = BkAidevAgentCallbackHandler(
            tracer=self.tracer,
            parent_trace_context=execute_kwargs.caller_trace_context,
            enabled=self.config.enabled,
            enable_traces=self.config.enable_traces,
            enable_metrics=self.config.enable_metrics,
            debug=self.config.debug,
            max_input_attribute_length=self.config.max_input_attribute_length,
            max_output_attribute_length=self.config.max_output_attribute_length,
            agent_id=agent_info.get("agent_id"),
            agent_code=agent_info.get("agent_code"),
            agent_name=agent_info.get("agent_name"),
            agent_sdk_version=agent_info.get("agent_sdk_version"),
            session_code=execute_kwargs.session_code,
            caller_executor=execute_kwargs.caller_executor,
            injector=injector,
            start_inputs=user_input,
            start_execute_kwargs=execute_kwargs,
            start_agent_info=agent_info,
        )
        callbacks.append(callback_handler)
        return agent, cfg
