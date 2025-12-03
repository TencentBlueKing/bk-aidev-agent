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
from datetime import timezone, timedelta, datetime
from typing import Collection, Optional

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from wrapt import wrap_function_wrapper
from aidev_bkplugin.services.agent import get_agent_config_info

from .callback_handler import BkAidevAgentCallbackHandler
from .config import OTelConfig, default_config
from .otel_service import BkAgentOTelService

logger = logging.getLogger(__name__)
_instruments = ("langchain-core > 0.1.0", )


class BkAidevAgentInstrumentor(BaseInstrumentor):
    def __init__(self, config: Optional[OTelConfig] = None):
        self._otel_service_config = config or default_config
        # 如果 instrument 的时候，没有提供 tracer， 那么由 instrument 提供 otel_service
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
        # wrap_function_wrapper(
        #     module="aidev_agent.core.extend.agent.qa",
        #     name="IntentRecognitionMixin.intent_recognition",
        #     wrapper=IntentRecognitionMixinIntentRecognition(),
        # )
        # 注入启动时的各个Agent
        wrap_function_wrapper(
            module="aidev_agent.core.agent.multimodal",
            name="LiteEnhancedAgentExecutor.stream_events",
            wrapper=LiteEnhancedAgentExecutorStreamEventsWrapper(tracer, self._otel_service_config),
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
        # unwrap("langchain_core.callbacks", "BaseCallbackManager.__init__")
        unwrap("aidev_agent.core.extend.intent.intent_recognition", "IntentRecognition.exec_intent_recognition")
        unwrap("aidev_agent.core.agent.multimodal", "LiteEnhancedAgentExecutor.stream_events")


class IntentRecognitionMixinIntentRecognition:
    def get_attributes(self,
        query: str,
        llm,
        tools,
        callbacks,
        chat_history,
        agent_options = None,
        **kwargs
    ):
        trace_cb = None
        if callbacks:
            if isinstance(callbacks, (list, tuple)):
                callbacks_list = callbacks
            elif hasattr(callbacks, "handlers"):
                # CallbackManager / AsyncCallbackManager
                callbacks_list = callbacks.handlers
            else:
                callbacks_list = [callbacks]
            for cb in callbacks_list:
                if isinstance(cb, BkAidevAgentCallbackHandler):
                    trace_cb = cb
                    break
        ret = {
            "query": query,
            "trace_cb": trace_cb,
        }
        if agent_options is not None:
            kb_options = agent_options.knowledge_query_options
            ret.update({
                "knowledge_bases": [kb.get("id") for kb in kb_options.knowledge_bases],
                "knowledge_items": [ki.get("id") for ki in kb_options.knowledge_items],
            })
        return ret

    def __call__(self, wrapped, instance, args, kwargs):
        ret = self.get_attributes(*args, **kwargs)
        trace_cb = ret["trace_cb"]
        query = ret["query"]
        if trace_cb is not None:
            with trace_cb.create_custom_span("rag.retrieval") as span:
                tz_cn = timezone(timedelta(hours=8))
                now = datetime.now(tz_cn)
                start_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
                start_time_unix_nano = int(now.timestamp() * 1_000_000_000)
                span.set_attribute("rag.start_time", start_time_str)
                span.set_attribute("rag.start_time_unix_nano", start_time_unix_nano)
                span.set_attribute("rag.query", query)
                span.set_attribute("rag.knowledge_bases", ret.get("knowledge_bases", []))
                span.set_attribute("rag.knowledge_items", ret.get("knowledge_items", []))
                ret = wrapped(*args, **kwargs)
                now = datetime.now(tz_cn)
                end_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
                end_time_unix_nano = int(now.timestamp() * 1_000_000_000)
                span.set_attribute("rag.end_time_str", end_time_str)
                span.set_attribute("rag.end_time_unix_nano", end_time_unix_nano)
                span.set_attribute("rag.num_retrieved_docs", len(kwargs.get("context", [])))
                span.set_attribute("rag.retrieved_docs", kwargs.get("retrieved_docs"))
        else:
            ret = wrapped(*args, **kwargs)
        return ret


class LiteEnhancedAgentExecutorStreamEventsWrapper:
    def __init__(self, tracer, config: OTelConfig):
        """
        初始化包装器
        """
        self.tracer = tracer
        self.config = config

    def get_values(self, input = None, **kwargs):
        from aidev_agent.core.utils.local import request_local
        ret = {"inputs": input}
        if hasattr(request_local, "otel_info"):
            if "executor" in  request_local.otel_info:
                ret["executor"] = request_local.otel_info["executor"]
            if "call_system_bk_app_code" in request_local.otel_info:
                ret["call_system_bk_app_code"] = request_local.otel_info["call_system_bk_app_code"]
            if "call_system_ai_type" in request_local.otel_info:
                ret["call_system_ai_type"] = request_local.otel_info["call_system_ai_type"]
            if "session_id" in request_local.otel_info:
                ret["session_id"] = request_local.otel_info["session_id"]
        return ret

    def __call__(
        self,
        wrapped,
        instance,
        args,
        kwargs,
    ):
        if "config" not in kwargs or "callbacks" not in kwargs["config"]:
            raise ValueError("LiteEnhancedAgentExecutor 调用过程中 必须传入callbacks")
        callback_handler = BkAidevAgentCallbackHandler(
            tracer=self.tracer,
            enabled=self.config.enabled,
            enable_traces=self.config.enable_traces,
            debug=self.config.debug,
            max_attribute_length=self.config.max_attribute_length,
        )
        kwargs["config"]["callbacks"].append(callback_handler)
        values = self.get_values(*args, **kwargs)
        agent = instance.agent
        values.update({
            "model_name": getattr(agent.llm, "model_name", None) or getattr(agent.llm, "model", None),
            "tools": [tool.name for tool in getattr(agent, "tools", [])],
            "agent_info": get_agent_config_info()
        })
        if hasattr(agent, "agent_options"):
            kb_options = agent.agent_options.knowledge_query_options
            values.update({
                "knowledge_bases": [kb.get("id") for kb in kb_options.knowledge_bases],
                "knowledge_items": [ki.get("id") for ki in kb_options.knowledge_items],
            })

        callback_handler.on_bk_agent_start(**values)
        yield from wrapped(*args, **kwargs)
        callback_handler.on_bk_agent_end(**values)
