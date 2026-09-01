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

import json
import os
from typing import Any, AsyncIterator, Iterator, Optional, Type, Union

import openai
import requests
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult, LLMResult
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import (
    ensure_config,
    get_async_callback_manager_for_config,
    get_callback_manager_for_config,
    patch_config,
)
from langchain_core.runnables.fallbacks import RunnableWithFallbacks
from langchain_openai.chat_models import ChatOpenAI as RawChatOpenAI
from langchain_openai.chat_models.base import _convert_message_to_dict
from langchain_openai.embeddings import OpenAIEmbeddings as RawOpenAIEmbeddings
from pydantic import BaseModel, PrivateAttr, model_validator

from aidev_agent.api.domains import BKAIDEV_URL
from aidev_agent.config import settings
from aidev_agent.exceptions import AIDevException
from aidev_agent.utils.datetimes import get_current_timestamp_in_milliseconds

try:
    from aidev_agent.packages.opentelemetry.resilience import (
        begin_model_attempt,
        finish_model_attempt_error,
        finish_model_attempt_success,
        propagate_model_failure,
        record_model_fallback_result,
        record_model_fallback_switch,
    )
except ImportError:  # OpenTelemetry is an optional SDK extra.
    begin_model_attempt = None
    finish_model_attempt_error = None
    finish_model_attempt_success = None
    propagate_model_failure = None
    record_model_fallback_result = None
    record_model_fallback_switch = None


def _runnable_model_name(runnable: Any) -> str:
    current = runnable
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        model_name = getattr(current, "model_name", None)
        if model_name:
            return str(model_name)
        current = getattr(current, "bound", None) or getattr(current, "runnable", None)
    return "unknown"


class _FallbackObservationHandler(BaseCallbackHandler):
    """Observe one RunnableWithFallbacks invocation without sharing state across runs."""

    run_inline = True

    def __init__(self, primary_model: str, fallback_models: list[str]):
        self.primary_model = primary_model
        self.fallback_models = fallback_models
        self._roles_by_run_id: dict[Any, tuple[str, str]] = {}
        self._primary_error: BaseException | None = None
        self._fallback_index = 0

    @property
    def primary_error(self) -> BaseException | None:
        return self._primary_error

    @staticmethod
    def _request_model(kwargs: dict[str, Any]) -> str | None:
        invocation_params = kwargs.get("invocation_params") or {}
        return invocation_params.get("model") or invocation_params.get("model_name")

    @staticmethod
    def _response_model(response: LLMResult) -> str | None:
        output = response.llm_output or {}
        return output.get("model_name") or output.get("model_id") or output.get("model")

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs) -> None:
        del serialized, messages
        request_model = self._request_model(kwargs)
        if self._primary_error is None:
            self._roles_by_run_id[run_id] = ("primary", request_model or self.primary_model)
            return

        fallback_model = request_model or self.fallback_models[min(self._fallback_index, len(self.fallback_models) - 1)]
        self._roles_by_run_id[run_id] = ("fallback", fallback_model)
        self._fallback_index += 1
        if record_model_fallback_switch is not None:
            record_model_fallback_switch(
                trigger_error=self._primary_error,
                primary_model=self.primary_model,
                fallback_model=fallback_model,
            )

    def on_llm_end(self, response: LLMResult, *, run_id, **kwargs) -> None:
        del kwargs
        role, request_model = self._roles_by_run_id.pop(run_id, ("primary", self.primary_model))
        if role == "fallback" and self._primary_error is not None and record_model_fallback_result is not None:
            record_model_fallback_result(
                outcome="succeeded",
                trigger_error=self._primary_error,
                primary_model=self.primary_model,
                fallback_model=request_model,
                response_model=self._response_model(response) or request_model,
            )

    def on_llm_error(self, error: BaseException, *, run_id, **kwargs) -> None:
        del kwargs
        role, request_model = self._roles_by_run_id.pop(run_id, ("primary", self.primary_model))
        if role == "primary":
            self._primary_error = error
            return
        if self._primary_error is not None and record_model_fallback_result is not None:
            record_model_fallback_result(
                outcome="failed",
                trigger_error=self._primary_error,
                primary_model=self.primary_model,
                fallback_model=request_model,
                fallback_error=error,
            )


class ObservableRunnableWithFallbacks(RunnableWithFallbacks):
    """Add per-invocation fallback observations while preserving LangChain behavior."""

    def _observed_config(
        self,
        config: RunnableConfig | None,
        *,
        is_async: bool,
    ) -> tuple[RunnableConfig, _FallbackObservationHandler]:
        normalized = ensure_config(config)
        observer = _FallbackObservationHandler(
            primary_model=_runnable_model_name(self.runnable),
            fallback_models=[_runnable_model_name(item) for item in self.fallbacks],
        )
        manager = (
            get_async_callback_manager_for_config(normalized)
            if is_async
            else get_callback_manager_for_config(normalized)
        )
        manager.add_handler(observer, inherit=True)
        return patch_config(normalized, callbacks=manager), observer

    def _propagate_primary_failure(self, observer: _FallbackObservationHandler) -> None:
        if observer.primary_error is not None and propagate_model_failure is not None:
            propagate_model_failure(
                model_role="primary",
                request_model=_runnable_model_name(self.runnable),
                error=observer.primary_error,
            )

    def invoke(self, input: Any, config: RunnableConfig | None = None, **kwargs: Any) -> Any:
        observed_config, observer = self._observed_config(config, is_async=False)
        try:
            return super().invoke(input, observed_config, **kwargs)
        except Exception:
            self._propagate_primary_failure(observer)
            raise

    async def ainvoke(self, input: Any, config: RunnableConfig | None = None, **kwargs: Any) -> Any:
        observed_config, observer = self._observed_config(config, is_async=True)
        try:
            return await super().ainvoke(input, observed_config, **kwargs)
        except Exception:
            self._propagate_primary_failure(observer)
            raise

    def stream(self, input: Any, config: RunnableConfig | None = None, **kwargs: Any) -> Iterator[Any]:
        observed_config, observer = self._observed_config(config, is_async=False)
        try:
            yield from super().stream(input, observed_config, **kwargs)
        except Exception:
            self._propagate_primary_failure(observer)
            raise

    async def astream(self, input: Any, config: RunnableConfig | None = None, **kwargs: Any) -> AsyncIterator[Any]:
        observed_config, observer = self._observed_config(config, is_async=True)
        try:
            async for item in super().astream(input, observed_config, **kwargs):
                yield item
        except Exception:
            self._propagate_primary_failure(observer)
            raise


class ApiGwMixin(BaseModel):
    @classmethod
    def get_setup_instance(cls, **kwargs):
        base_url = kwargs.get("base_url", "") or settings.LLM_GW_ENDPOINT
        if not base_url:
            base_url = f"{BKAIDEV_URL}/openapi/aidev/gateway/llm/v1"
        kwargs["base_url"] = base_url
        auth_headers = kwargs.pop("auth_headers", {})
        session_code = kwargs.pop("session_code", None)
        if not auth_headers:
            auth_headers = {
                "bk_app_code": settings.APP_CODE,
                "bk_app_secret": settings.SECRET_KEY,
            }
        if "default_headers" in kwargs:
            kwargs["default_headers"].update({"X-Bkapi-Authorization": json.dumps(auth_headers)})
        else:
            kwargs["default_headers"] = {"X-Bkapi-Authorization": json.dumps(auth_headers)}
        # 调用方显式提供 X-Session-ID 时不覆盖
        if session_code:
            kwargs["default_headers"].setdefault("X-Session-ID", session_code)
        return cls(**kwargs)


class ChatModel(RawChatOpenAI, ApiGwMixin):
    remote_tokenizer: bool = True
    max_content_length: Optional[int] = None
    fallback_model: str | None = None
    retry_strategy: str | None = None
    _owns_http_async_client: bool = PrivateAttr(default=False)
    _model_role: str = PrivateAttr(default="primary")

    @classmethod
    def get_setup_instance(cls, **kwargs) -> "ChatModel | RunnableWithFallbacks":
        """创建网关模型；配置备用模型时返回 LangChain fallback Runnable。"""
        owns_http_async_client = False
        if kwargs.get("http_async_client") is None and kwargs.get("async_client") is None:
            kwargs["http_async_client"] = openai.DefaultAsyncHttpxClient()
            owns_http_async_client = True

        model = super().get_setup_instance(**kwargs)
        model._owns_http_async_client = owns_http_async_client
        fallback = model._get_fallback_model()
        if fallback is None:
            return model
        return ObservableRunnableWithFallbacks(runnable=model, fallbacks=[fallback])

    @model_validator(mode="before")
    @classmethod
    def set_tiktoken_model_name_based_on_model_name(cls, values):
        if "api_key" not in values:
            values["api_key"] = "empty"
        return values

    def get_num_tokens(self, text: str) -> int:
        if not self.remote_tokenizer:
            return super().get_num_tokens(text)
        data = dict(
            prompts=[
                dict(
                    model=self.model_name,
                    prompt=text,
                    max_tokens=self.max_tokens or 1024,
                    max_content_length=self.max_content_length,
                )
            ]
        )
        endpoint = os.path.join(self.openai_api_base, "api/token_check")
        try:
            resp = requests.post(
                endpoint,
                headers=self.default_headers,
                json=data,
                timeout=settings.REQUEST_API_TIMEOUT,
            )
            resp.raise_for_status()
            result = resp.json()
            return result["prompts"][0]["tokenCount"]
        except requests.HTTPError as err:
            try:
                error_message = err.response.json()
                raise AIDevException(message=f"模型获取token异常: {error_message}")
            except json.JSONDecodeError:
                raise AIDevException(message=f"模型获取token异常: {err.response.content.decode(errors='ignore')}")

    def get_num_tokens_from_messages(self, messages: list[BaseMessage]) -> int:
        if not self.remote_tokenizer:
            return super().get_num_tokens_from_messages(messages)
        messages_dict = [_convert_message_to_dict(m) for m in messages]
        return self.get_num_tokens(json.dumps(messages_dict))

    def _get_request_payload(self, *args, **kwargs) -> dict:
        payload = super()._get_request_payload(*args, **kwargs)
        # 部分 langchain-openai 版本会将子类扩展字段合并到 OpenAI 请求参数中。
        # fallback_model 仅用于 SDK 内部切换，不能透传给 OpenAI 客户端。
        payload.pop("fallback_model", None)
        payload.pop("retry_strategy", None)
        for message in payload.get("messages", []):
            if message.get("role") != "user" or not isinstance(message.get("content"), list):
                continue
            content = []
            for item in message["content"]:
                if (
                    isinstance(item, dict)
                    and item.get("type") == "binary"
                    and str(item.get("mime_type") or "").startswith("image/")
                ):
                    image_url = item.get("url")
                    if not image_url and item.get("data"):
                        image_url = f"data:{item['mime_type']};base64,{item['data']}"
                    if image_url:
                        content.append({"type": "image_url", "image_url": {"url": image_url}})
                        continue
                content.append(item)
            message["content"] = content
        return payload

    def _create_chat_result(
        self,
        response: Union[dict, openai.BaseModel],
        generation_info: Optional[dict] = None,
    ) -> ChatResult:
        rtn = super()._create_chat_result(response, generation_info)

        if not isinstance(response, openai.BaseModel):
            return rtn

        if hasattr(response.choices[0].message, "reasoning_content"):  # type: ignore
            rtn.generations[0].message.additional_kwargs["reasoning_content"] = response.choices[
                0
            ].message.reasoning_content  # type: ignore

        return rtn

    def _get_fallback_model(self) -> "ChatModel | None":
        if not self.fallback_model or self.fallback_model == self.model_name:
            return None
        fallback = self.model_copy(update={"model_name": self.fallback_model, "fallback_model": None})
        fallback._model_role = "fallback"
        return fallback

    def _begin_model_observation(self):
        if begin_model_attempt is None:
            return None
        return begin_model_attempt(
            model_role=self._model_role,
            request_model=self.model_name or "unknown",
        )

    def _finish_model_observation_success(self, handle) -> None:
        if handle is not None and finish_model_attempt_success is not None:
            finish_model_attempt_success(handle)

    def _finish_model_observation_error(self, handle, error: BaseException) -> None:
        if handle is not None and finish_model_attempt_error is not None:
            finish_model_attempt_error(handle, error, retry_strategy=settings.LLM_RETRY_STRATEGY)

    def _generate(self, *args, **kwargs) -> ChatResult:
        handle = self._begin_model_observation()
        try:
            result = super()._generate(*args, **kwargs)
        except Exception as error:
            self._finish_model_observation_error(handle, error)
            raise
        self._finish_model_observation_success(handle)
        return result

    async def _agenerate(self, *args, **kwargs) -> ChatResult:
        handle = self._begin_model_observation()
        try:
            result = await super()._agenerate(*args, **kwargs)
        except Exception as error:
            self._finish_model_observation_error(handle, error)
            raise
        self._finish_model_observation_success(handle)
        return result

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: Type,
        base_generation_info: Optional[dict],
    ) -> Optional[ChatGenerationChunk]:
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )
        if (choices := chunk.get("choices")) and generation_chunk:
            top = choices[0]
            reasoning_content = top.get("delta", {}).get("reasoning_content")
            if reasoning_content and isinstance(generation_chunk.message, AIMessageChunk):
                generation_chunk.message.additional_kwargs["reasoning_content"] = reasoning_content
        return generation_chunk

    def _process_reasoning_chunk(
        self,
        chunk: ChatGenerationChunk,
        reasoning_start_time: int = 0,
        last_reasoning_content: str = "",
    ) -> tuple[ChatGenerationChunk, int, str]:
        """处理 reasoning_content 字段的时间统计逻辑

        Args:
            chunk: 当前的生成块
            reasoning_start_time: reasoning 开始时间戳（0表示未开始）
            last_reasoning_content: 上一个块的 reasoning_content

        Returns:
            处理后的 (chunk, 更新后的开始时间, 当前的reasoning_content)
        """
        current_reasoning_content = chunk.message.additional_kwargs.get("reasoning_content")

        # 记录 reasoning 开始时间
        if current_reasoning_content and reasoning_start_time == 0:
            reasoning_start_time = get_current_timestamp_in_milliseconds()

        # 计算 reasoning 结束时间
        if last_reasoning_content and not current_reasoning_content:
            reasoning_end_time = get_current_timestamp_in_milliseconds()
            chunk.message.additional_kwargs["reasoning_time"] = reasoning_end_time - reasoning_start_time

        return chunk, reasoning_start_time, current_reasoning_content or ""

    def _stream(self, *args, **kwargs) -> Iterator[ChatGenerationChunk]:
        """对reasoning_content字段进行时间统计"""
        handle = self._begin_model_observation()
        reasoning_start_time = 0
        last_reasoning_content = ""
        try:
            for chunk in super()._stream(*args, **kwargs):
                chunk, reasoning_start_time, last_reasoning_content = self._process_reasoning_chunk(
                    chunk, reasoning_start_time, last_reasoning_content
                )
                yield chunk
        except Exception as error:
            self._finish_model_observation_error(handle, error)
            raise
        self._finish_model_observation_success(handle)

    async def _astream(self, *args, **kwargs) -> AsyncIterator[ChatGenerationChunk]:
        """对reasoning_content字段进行时间统计"""
        handle = self._begin_model_observation()
        reasoning_start_time = 0
        last_reasoning_content = ""
        try:
            async for chunk in super()._astream(*args, **kwargs):
                chunk, reasoning_start_time, last_reasoning_content = self._process_reasoning_chunk(
                    chunk, reasoning_start_time, last_reasoning_content
                )
                yield chunk
        except Exception as error:
            self._finish_model_observation_error(handle, error)
            raise
        self._finish_model_observation_success(handle)


ChatModelRunnable = RunnableWithFallbacks | BaseChatModel


class Embeddings(RawOpenAIEmbeddings, ApiGwMixin):
    @model_validator(mode="before")
    @classmethod
    def set_check_embedding_ctx_length_based_on_model_name(cls, values):
        model = values.get("model_name") or values.get("model")
        if model and not (model.startswith("text-embedding")):
            values["check_embedding_ctx_length"] = False
            values["tiktoken_model_name"] = "gpt-3.5-turbo"
        values["chunk_size"] = 100
        if "api_key" not in values:
            values["api_key"] = "empty"
        return values
