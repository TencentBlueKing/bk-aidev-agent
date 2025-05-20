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

from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from langchain_core.outputs import ChatGeneration, LLMResult

try:
    from langfuse.callback import CallbackHandler
    from langfuse.callback.langchain import _extract_raw_esponse, _parse_usage_model
    from langfuse.utils.langfuse_singleton import LangfuseSingleton

    LANGFUSE_INSTALLED = True
except ImportError:
    LANGFUSE_INSTALLED = False


if LANGFUSE_INSTALLED:

    def _parse_usage(response: LLMResult):
        llm_usage_keys = ["token_usage", "usage"]
        llm_usage = None
        if response.llm_output is not None:
            for key in llm_usage_keys:
                if key in response.llm_output and response.llm_output[key]:
                    usage = response.llm_output[key]
                    if hasattr(usage, "to_dict_recursive"):
                        usage = usage.to_dict_recursive()
                    llm_usage = _parse_usage_model(usage)
                    break
        return llm_usage

    current_langchain_run_info: ContextVar = ContextVar("current_langchain_run_info")

    class EnhancedLangfuseCallbackHandler(CallbackHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.current_langchain_run_info_reset_token = []

        def on_tool_start(
            self,
            serialized: Dict[str, Any],
            input_str: str,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            tags: Optional[List[str]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            **kwargs: Any,
        ) -> Any:
            t = current_langchain_run_info.set(
                {"serialized": serialized, "run_id": run_id, "parent_run_id": parent_run_id}
            )
            self.current_langchain_run_info_reset_token.append(t)
            try:
                super().on_tool_start(
                    serialized,
                    input_str,
                    run_id=run_id,
                    parent_run_id=parent_run_id,
                    tags=tags,
                    metadata=metadata,
                    **kwargs,
                )
            except BaseException:
                current_langchain_run_info.reset(self.current_langchain_run_info_reset_token.pop())
                raise

        def on_tool_end(
            self,
            output: str,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
        ) -> Any:
            try:
                super().on_tool_end(output, run_id=run_id, parent_run_id=parent_run_id, **kwargs)
            finally:
                current_langchain_run_info.reset(self.current_langchain_run_info_reset_token.pop())

        def on_tool_error(
            self,
            error: Union[Exception, KeyboardInterrupt],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
        ) -> Any:
            try:
                super().on_tool_error(error, run_id=run_id, parent_run_id=parent_run_id, **kwargs)
            finally:
                current_langchain_run_info.reset(self.current_langchain_run_info_reset_token.pop())

        def on_chain_error(
            self,
            error: Union[Exception, KeyboardInterrupt],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
        ) -> Any:
            super().on_chain_error(error, run_id=run_id, parent_run_id=parent_run_id, **kwargs)

        def on_llm_error(
            self,
            error: Union[Exception, KeyboardInterrupt],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
        ) -> Any:
            super().on_llm_error(error, run_id=run_id, parent_run_id=parent_run_id, **kwargs)

        def on_chain_start(
            self,
            serialized: Dict[str, Any],
            inputs: Dict[str, Any],
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            tags: Optional[List[str]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            **kwargs: Any,
        ) -> Any:
            parent_run_info = current_langchain_run_info.get(None)
            if not parent_run_id and parent_run_info:
                parent_run_id = parent_run_info["run_id"]
            super().on_chain_start(
                serialized, inputs, run_id=run_id, parent_run_id=parent_run_id, tags=tags, metadata=metadata, **kwargs
            )

        def on_llm_end(
            self,
            response: LLMResult,
            *,
            run_id: UUID,
            parent_run_id: Optional[UUID] = None,
            **kwargs: Any,
        ) -> Any:
            try:
                self.log.debug(
                    f"on llm end: run_id: {run_id} parent_run_id: {parent_run_id} response: {response} kwargs: {kwargs}"
                )
                if run_id not in self.runs:
                    raise Exception("Run not found, see docs what to do in this case.")
                else:
                    generation = response.generations[-1][-1]
                    extracted_response = (
                        self._convert_message_to_dict(generation.message)
                        if isinstance(generation, ChatGeneration)
                        else _extract_raw_esponse(generation)
                    )

                    llm_usage = _parse_usage(response)
                    self.runs[run_id] = self.runs[run_id].end(
                        output=extracted_response, usage=llm_usage, version=self.version
                    )

                    self._update_trace(run_id, parent_run_id, extracted_response)

            except Exception as e:
                self.log.exception(e)

    def get_langfuse_callback(
        username: str, name: str = "CommonAgent", **kwargs
    ) -> Optional[EnhancedLangfuseCallbackHandler]:
        # username 必传，结合django框架可以再考虑封装一层通过request 获取 username
        langfuse_callback = EnhancedLangfuseCallbackHandler(
            stateful_client=LangfuseSingleton()
            .get()
            .trace(
                session_id=kwargs.get("session_id", uuid4().__str__()),
                user_id=kwargs.get("user_id", "") or username,
                id=kwargs.get("id", uuid4().__str__()),
                name=name,
            )
        )
        return langfuse_callback
