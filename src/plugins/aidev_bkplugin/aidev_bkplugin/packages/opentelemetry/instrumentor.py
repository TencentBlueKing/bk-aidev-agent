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
from aidev_agent.core.utils.local import request_local
from aidev_agent.services.pydantic_models import ExecuteKwargs
from asgiref.sync import sync_to_async
from langchain_core.runnables import RunnableConfig
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from wrapt import wrap_function_wrapper

from aidev_bkplugin.packages.opentelemetry.utils import dont_throw
from aidev_bkplugin.services.agent import get_agent_config_info

from .callback_handler import BkAidevAgentCallbackHandler, BkAidevAgentInjector
from .config import OTelConfig, default_config
from .otel_service import BkAgentOTelService

logger = logging.getLogger(__name__)
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

        # 根据 aidev_agent 的包版本注入到不同的对象中
        # 意图识别注入 - 用于获取知识库查询结果
        wrap_function_wrapper(
            module="aidev_agent.core.extend.intent.intent_recognition",
            name="IntentRecognition.exec_intent_recognition",
            wrapper=IntentRecognitionMixinIntentRecognition(),
        )

        # 注入启动时的各个Agent
        wrap_function_wrapper(
            module="aidev_agent.core.agent.multimodal",
            name="LiteEnhancedAgentExecutor.stream_events",
            wrapper=LiteEnhancedAgentExecutorStreamEventsWrapper(tracer, self._otel_service_config),
        )
        wrap_function_wrapper(
            module="aidev_agent.core.agent.multimodal",
            name="EnhancedAgentExecutor.invoke",
            wrapper=LiteEnhancedAgentExecutorInvokeWrapper(tracer, self._otel_service_config),
        )
        wrap_function_wrapper(
            module="aidev_agent.core.agent.multimodal",
            name="EnhancedAgentExecutor.ainvoke",
            wrapper=LiteEnhancedAgentExecutorAInvokeWrapper(tracer, self._otel_service_config),
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
        unwrap("aidev_agent.core.extend.intent.intent_recognition", "IntentRecognition.exec_intent_recognition")
        unwrap("aidev_agent.core.agent.multimodal", "LiteEnhancedAgentExecutor.stream_events")
        unwrap("aidev_agent.core.agent.multimodal", "EnhancedAgentExecutor.invoke")
        unwrap("aidev_agent.core.agent.multimodal", "EnhancedAgentExecutor.ainvoke")


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


class IntentRecognitionMixinIntentRecognition:
    def get_attributes(self, query: str, llm, tools, callbacks, chat_history, agent_options=None, **kwargs):
        trace_cb = _get_trace_cb_from_callbacks(callbacks)
        attributes: Dict[str, Any] = {"rag.query": query}
        if agent_options is not None:
            kb_options = agent_options.knowledge_query_options
            attributes.update(
                {
                    "rag.knowledge_bases": [kb.get("id") for kb in kb_options.knowledge_bases],
                    "rag.knowledge_items": [ki.get("id") for ki in kb_options.knowledge_items],
                }
            )
            if hasattr(kb_options, "model_dump"):
                attributes["rag.kb_options"] = orjson.dumps(kb_options.model_dump(mode="json"))
        return trace_cb, attributes

    def get_id_by_docs(self, docs):
        if isinstance(docs, list):
            return [i.get("id") for i in docs]
        return []

    @dont_throw
    def _on_end(self, span, kwargs):
        if kwargs.get("knowledge_resources_emb_recalled"):
            span.set_attribute(
                "rag.knowledge_resources_emb_recalled",
                orjson.dumps(self.get_id_by_docs(kwargs.get("knowledge_resources_emb_recalled"))),
            )
        if kwargs.get("knowledge_resources_highly_relevant"):
            span.set_attribute(
                "rag.knowledge_resources_highly_relevant",
                orjson.dumps(self.get_id_by_docs(kwargs.get("knowledge_resources_highly_relevant"))),
            )
        if kwargs.get("knowledge_resources_moderately_relevant"):
            span.set_attribute(
                "rag.knowledge_resources_moderately_relevant",
                orjson.dumps(self.get_id_by_docs(kwargs.get("knowledge_resources_moderately_relevant"))),
            )

    def __call__(self, wrapped, instance, args, kwargs):
        trace_cb, attributes = self.get_attributes(*args, **kwargs)
        if trace_cb is not None:
            with trace_cb.create_custom_span("rag.retrieval", attributes=attributes) as span:
                ret = wrapped(*args, **kwargs)
                self._on_end(span, ret)
        else:
            ret = wrapped(*args, **kwargs)
        return ret


class LiteEnhancedAgentExecutorWrapper:
    def __init__(self, tracer, config: OTelConfig):
        """
        初始化包装器
        """
        self.tracer = tracer
        self.config = config

    def get_config(self, input: dict[str, Any], config: Optional[RunnableConfig] = None, **kwargs: Any):
        return config

    def get_values(self, agent, input: dict[str, Any] = None, *args, **kwargs):
        if input is None:
            logger.warning("用户调用Agent时没有传入任何数据，user_input 为 None, execute_kwargs 不处理")
            input = {}

        # 用户输入
        user_input = input.get("input")
        # 调用相关参数
        execute_kwargs = ExecuteKwargs()
        if isinstance(input, dict) and "execute_kwargs" in input and isinstance(execute_kwargs, ExecuteKwargs):
            execute_kwargs = input.pop("execute_kwargs")
        if hasattr(request_local, "otel_info"):
            for k, v in request_local.otel_info.items():
                if hasattr(execute_kwargs, k) and getattr(execute_kwargs, k) is None:
                    setattr(execute_kwargs, k, v)
        # Agent 相关参数
        agent_info = get_agent_config_info()  # get_agent_config_info 实现了缓存机制
        agent_info.pop("otel_info")
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

    def create_callback_handler(self, *args, **kwargs):
        config = self.get_config(*args, **kwargs)
        if config is None:
            raise ValueError("LiteEnhancedAgentExecutor 调用过程中 必须传入config")

        callbacks = config.setdefault("callbacks", [])

        callback_handler = BkAidevAgentCallbackHandler(
            tracer=self.tracer,
            enabled=self.config.enabled,
            enable_traces=self.config.enable_traces,
            debug=self.config.debug,
            max_attribute_length=self.config.max_attribute_length,
        )
        callbacks.append(callback_handler)
        return callback_handler


class LiteEnhancedAgentExecutorStreamEventsWrapper(LiteEnhancedAgentExecutorWrapper):
    def __call__(
        self,
        wrapped,
        instance,
        args,
        kwargs,
    ):
        values = self.get_values(instance.agent, *args, **kwargs)
        base_handler = BkAidevAgentInjector(tracer=self.tracer, parent_trace_context=values.get("parent_trace_context"))
        self.create_callback_handler(*args, **kwargs)
        try:
            base_handler.on_bk_agent_start(**values)
            yield from wrapped(*args, **kwargs)
        finally:
            base_handler.on_bk_agent_end(**values)


class LiteEnhancedAgentExecutorInvokeWrapper(LiteEnhancedAgentExecutorWrapper):
    def __call__(
        self,
        wrapped,
        instance,
        args,
        kwargs,
    ):
        values = self.get_values(instance.agent, *args, **kwargs)
        self.create_callback_handler(*args, **kwargs)
        base_handler = BkAidevAgentInjector(tracer=self.tracer, parent_trace_context=values.get("parent_trace_context"))
        base_handler.on_bk_agent_start(**values)
        ret = wrapped(*args, **kwargs)
        base_handler.on_bk_agent_end(**values)
        return ret


class LiteEnhancedAgentExecutorAInvokeWrapper(LiteEnhancedAgentExecutorWrapper):
    async def __call__(
        self,
        wrapped,
        instance,
        args,
        kwargs,
    ):
        values = await sync_to_async(self.get_values)(instance.agent, *args, **kwargs)
        base_handler = BkAidevAgentInjector(tracer=self.tracer, parent_trace_context=values.get("parent_trace_context"))
        self.create_callback_handler(*args, **kwargs)
        base_handler.on_bk_agent_start(**values)
        ret = await wrapped(*args, **kwargs)
        base_handler.on_bk_agent_end(**values)
        return ret
