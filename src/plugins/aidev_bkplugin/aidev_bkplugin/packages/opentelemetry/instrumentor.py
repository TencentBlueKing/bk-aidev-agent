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

import inspect
import logging
from typing import Any, Collection, Dict, Generator, Iterator, Optional

import orjson
from aidev_agent.services.pydantic_models import ExecuteKwargs
from aidev_agent.utils.local import request_local
from langchain_core.messages import BaseMessage
from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from wrapt import wrap_function_wrapper

from aidev_bkplugin.services.agent import get_agent_config_info

from .callback_handler import BkAidevAgentCallbackHandler, BkAidevAgentInjector
from .config import OTelConfig, default_config
from .otel_service import BkAgentOTelService
from .utils import dont_throw

logger = logging.getLogger(__name__)

_E2B_BACKEND_MODULE = "aidev_agent.core.tools.e2b_sandbox.backend"
_E2B_ENSURE_SANDBOX = "E2BSandboxBackend._ensure_sandbox"
_E2B_PREPARE_SKILL_RUNTIME = "E2BSandboxBackend._prepare_skill_runtime"
_instruments = ("langchain-core > 0.1.0",)


class BkAidevAgentInstrumentor(BaseInstrumentor):
    """
    BkAidevAgentInstrumentor 对于 AidevAgent 进行了插桩
    为了避免由于全局设置的采样等原因导致公共数据收集不全
    默认使用由 BkAidevAgentInstrumentor 提供的 tracer_provider 而不是全局的 tracer_provider
    将在 instrument 的时候，启动 otel_service
    请注意，不要使用 BkAidevAgentInstrumentor().instrument() 多次，由于 BaseInstrumentor() 是单例化的，第二次会导致 trace 获取异常
    """

    def __init__(self, config: Optional[OTelConfig] = None):
        self._otel_service_config = config or default_config
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
        # 注入 Agent 启动的消息头
        wrap_function_wrapper(
            module="aidev_agent.services.agent.chat",
            name="ChatCompletionAgent._execute",
            wrapper=ChatCompletionAgentExecuteByAgentWrapper(tracer, self._otel_service_config),
        )
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
        # 注入 E2B 沙箱运行时的可观测性（使用全局 tracer，不依赖 otel_service 的 tracer）
        _global_tracer = trace.get_tracer(__name__)
        try:
            wrap_function_wrapper(
                module=_E2B_BACKEND_MODULE,
                name=_E2B_ENSURE_SANDBOX,
                wrapper=E2BEnsureSandboxWrapper(_global_tracer),
            )
            wrap_function_wrapper(
                module=_E2B_BACKEND_MODULE,
                name=_E2B_PREPARE_SKILL_RUNTIME,
                wrapper=E2BPrepareSkillRuntimeWrapper(_global_tracer),
            )
        except Exception:  # noqa: BLE001
            logger.debug("E2B sandbox backend not available, skipping E2B instrumentation")

    def _uninstrument(self, **kwargs):
        """
        取消自动插桩

        恢复 langchain_core.callbacks.BaseCallbackManager.__init__
        的原始实现。

        Returns:
            bool: 是否成功取消插桩
        """
        self.stop_otel_service()
        unwrap("aidev_agent.services.agent.chat", "ChatCompletionAgent._execute")
        unwrap("aidev_agent.services.agent.chat", "ChatCompletionAgent._get_agent")
        unwrap("aidev_agent.core.nodes.knowledge", "AgentKnowledgeNode.__call__")
        try:
            unwrap(_E2B_BACKEND_MODULE, _E2B_ENSURE_SANDBOX)
            unwrap(_E2B_BACKEND_MODULE, _E2B_PREPARE_SKILL_RUNTIME)
        except Exception:  # noqa: BLE001
            logger.debug("E2B sandbox backend not available, skipping E2B uninstrumentation")


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


class E2BEnsureSandboxWrapper:
    """E2BSandboxBackend._ensure_sandbox 的可观测性包装器。

    仅在沙箱首次创建时生成 ``e2b.ensure_sandbox`` span，
    已初始化的沙箱实例（幂等调用）不创建 span。
    """

    def __init__(self, tracer: trace.Tracer):
        self.tracer = tracer

    @dont_throw
    def __call__(self, wrapped, instance, args, kwargs):
        # 沙箱已初始化，跳过 span 创建
        if instance._sandbox is not None:
            return wrapped(*args, **kwargs)

        attributes = {
            "e2b.template": instance._template,
            "e2b.timeout": instance._timeout,
            "e2b.has_envs": bool(instance._pending_sandbox_env),
        }
        with self.tracer.start_as_current_span("e2b.ensure_sandbox", attributes=attributes) as span:
            try:
                result = wrapped(*args, **kwargs)
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            # 沙箱创建成功，补充 sandbox_info
            try:
                sandbox_info = instance.sandbox_info
                if sandbox_info:
                    for key, value in sandbox_info.items():
                        if value is not None:
                            span.set_attribute(f"e2b.{key}", str(value))
            except Exception:  # noqa: BLE001
                pass
            return result


class E2BPrepareSkillRuntimeWrapper:
    """E2BSandboxBackend._prepare_skill_runtime 的可观测性包装器。

    为 skill 打包上传解压过程生成 ``e2b.prepare_skill_runtime`` span。
    """

    def __init__(self, tracer: trace.Tracer):
        self.tracer = tracer

    @dont_throw
    def __call__(self, wrapped, instance, args, kwargs):
        skill_dir = args[0] if args else kwargs.get("skill_dir", "")
        skill_name = args[1] if len(args) > 1 else kwargs.get("skill_name", "")

        attributes = {
            "e2b.skill_dir": str(skill_dir),
            "e2b.skill_name": str(skill_name),
        }
        with self.tracer.start_as_current_span("e2b.prepare_skill_runtime", attributes=attributes) as span:
            try:
                return wrapped(*args, **kwargs)
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise


class ChatCompletionAgentExecuteByAgentWrapper:
    def __init__(self, tracer, config: OTelConfig):
        """
        初始化包装器
        """
        self.tracer = tracer
        self.config = config

    def get_values(self, messages: list[BaseMessage], execute_kwargs: ExecuteKwargs = None):
        # 用户输入
        if isinstance(messages, list) and len(messages) >= 1 and isinstance(messages[-1], BaseMessage):
            user_input = messages[-1].content
        else:
            logger.warning("用户调用Agent时没有传入任何数据，user_input 为 None, execute_kwargs 不处理")
            user_input = None
        # 调用相关参数
        execute_kwargs = execute_kwargs or ExecuteKwargs()
        if hasattr(request_local, "otel_info") and isinstance(request_local.otel_info, dict):
            for k, v in request_local.otel_info.items():
                if hasattr(execute_kwargs, k) and getattr(execute_kwargs, k) is None:
                    setattr(execute_kwargs, k, v)
        # Agent 相关参数
        agent_info = get_agent_config_info()  # get_agent_config_info 实现了缓存机制
        agent_info.pop("otel_info", None)
        # trace 链路追踪的参数
        parent_trace_context = execute_kwargs.caller_trace_context
        # 构建统一参数
        ret = {
            "inputs": user_input,
            "execute_kwargs": execute_kwargs,
            "agent_info": agent_info,
            "parent_trace_context": parent_trace_context,
        }
        return ret

    def _wrap_generator(
        self, gen: Iterator, base_handler: BkAidevAgentInjector, values: Dict[str, Any]
    ) -> Generator[Any, None, None]:
        """
        包装生成器/迭代器，确保在迭代完成或异常时正确触发 on_bk_agent_end

        Args:
            gen: 原始生成器/迭代器
            base_handler: BkAidevAgentInjector 实例
            values: 传递给 on_bk_agent_end 的参数

        Yields:
            原始生成器的每个元素
        """
        try:
            yield from gen
        except Exception as e:
            logger.exception("Agent 执行过程中发生异常")
            base_handler.on_bk_agent_end(**values, error=e)
            raise
        else:
            base_handler.on_bk_agent_end(**values)

    def __call__(
        self,
        wrapped,
        instance,
        args,
        kwargs,
    ):
        values = self.get_values(*args, **kwargs)
        base_handler = BkAidevAgentInjector(tracer=self.tracer, parent_trace_context=values.get("parent_trace_context"))

        base_handler.on_bk_agent_start(**values)
        # 获取 root span，注入到 caller_trace_context 以保证链路追踪不断掉
        # 直接从 base_handler 获取 root_span，不通过全局 context（避免 context 污染）
        execute_kwargs = values.get("execute_kwargs") or ExecuteKwargs()
        root_span = base_handler.root_span
        if root_span is not None and root_span.get_span_context().is_valid:
            carrier: dict[str, str] = {}
            propagator = TraceContextTextMapPropagator()
            propagator.inject(carrier, context=trace.set_span_in_context(root_span))
            execute_kwargs.caller_trace_context = carrier

        # 在当前 HTTP 请求线程上 attach root span，使得自动插桩（requests/redis 等）能关联 trace
        # 注意：必须在同一线程上 detach，因为 ContextVar 是线程隔离的
        # 在流式场景下，_wrap_generator 内的 on_bk_agent_end 在 producer 线程执行，
        # 无法 detach 当前线程的 context，所以必须在 __call__ 返回前 detach
        root_span_token = None
        if root_span is not None:
            root_span_token = context_api.attach(trace.set_span_in_context(root_span))

        try:
            result = wrapped(*args, **kwargs)
        except Exception as e:
            # 同步执行时发生异常，立即触发 on_end
            base_handler.on_bk_agent_end(**values, error=e)
            raise
        finally:
            # 无论同步还是流式，在当前 HTTP 线程上立即 detach
            # 流式场景：generator 的实际消费在 producer 线程，不在当前线程
            # 当前线程的职责到这里结束，必须清理 context 栈
            if root_span_token is not None:
                try:
                    context_api.detach(root_span_token)
                except Exception:  # noqa: BLE001
                    # 确保finally块中的清理操作不因detach失败而中断
                    logger.debug("Failed to detach root span context token", exc_info=True)

        # 判断返回值是否是生成器/迭代器
        if inspect.isgenerator(result) or inspect.isgeneratorfunction(result):
            # 流式返回：包装生成器，在迭代完成时触发 on_end
            return self._wrap_generator(result, base_handler, values)
        elif hasattr(result, "__iter__") and hasattr(result, "__next__"):
            # 其他迭代器类型（如自定义迭代器）
            return self._wrap_generator(result, base_handler, values)
        else:
            # 非流式返回：立即触发 on_end
            base_handler.on_bk_agent_end(**values)
            return result


class ChatCompletionAgentGetAgentWrapper:
    def __init__(self, tracer, config: OTelConfig):
        """
        初始化包装器
        """
        self.tracer = tracer
        self.config = config

    def __call__(
        self,
        wrapped,
        instance,
        args,
        kwargs,
    ):
        agent, cfg = wrapped(*args, **kwargs)
        callbacks = cfg.setdefault("callbacks", [])
        execute_kwargs = kwargs.get("execute_kwargs") or ExecuteKwargs()
        callback_handler = BkAidevAgentCallbackHandler(
            tracer=self.tracer,
            parent_trace_context=execute_kwargs.caller_trace_context,
            enabled=self.config.enabled,
            enable_traces=self.config.enable_traces,
            debug=self.config.debug,
            max_attribute_length=self.config.max_attribute_length,
        )
        callbacks.append(callback_handler)
        return agent, cfg
