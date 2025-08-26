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
from typing import Optional, Type, Union

import openai
import requests
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai.chat_models import ChatOpenAI as RawChatOpenAI
from langchain_openai.chat_models.base import _convert_message_to_dict
from langchain_openai.embeddings import OpenAIEmbeddings as RawOpenAIEmbeddings
from pydantic import BaseModel, model_validator

from aidev_agent.api.domains import BKAIDEV_URL
from aidev_agent.config import settings


class ApiGwMixin(BaseModel):
    @classmethod
    def get_setup_instance(cls, **kwargs):
        base_url = kwargs.get("base_url", "") or settings.LLM_GW_ENDPOINT
        if not base_url:
            base_url = f"{BKAIDEV_URL}/openapi/aidev/gateway/llm/v1"
        kwargs["base_url"] = base_url
        auth_headers = kwargs.pop("auth_headers", {})
        if not auth_headers:
            auth_headers = {
                "bk_app_code": settings.APP_CODE,
                "bk_app_secret": settings.SECRET_KEY,
            }
        if "default_headers" in kwargs:
            kwargs["default_headers"].update({"X-Bkapi-Authorization": json.dumps(auth_headers)})
        else:
            kwargs["default_headers"] = {"X-Bkapi-Authorization": json.dumps(auth_headers)}
        return cls(**kwargs)


class ChatModel(RawChatOpenAI, ApiGwMixin):
    remote_tokenizer: bool = True
    max_content_length: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def set_tiktoken_model_name_based_on_model_name(cls, values):
        model = values.get("model_name") or values.get("model")
        if model and not (model.startswith(("gpt-3.5-turbo", "gpt-4"))):
            values["tiktoken_model_name"] = "gpt-3.5-turbo"
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
        resp = requests.post(
            endpoint,
            headers=self.default_headers,
            json=data,
        )
        resp.raise_for_status()
        result = resp.json()
        return result["prompts"][0]["tokenCount"]

    def get_num_tokens_from_messages(self, messages: list[BaseMessage]) -> int:
        if not self.remote_tokenizer:
            return super().get_num_tokens_from_messages(messages)
        messages_dict = [_convert_message_to_dict(m) for m in messages]
        return self.get_num_tokens(json.dumps(messages_dict))

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
