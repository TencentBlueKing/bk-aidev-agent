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

import time
import traceback
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from logging import getLogger
from random import randint
from typing import Any, Iterator, List, Optional

import requests
from langchain_community.adapters.openai import convert_message_to_dict
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage, BaseMessageChunk
from langchain_core.outputs import ChatResult
from langchain_core.runnables import RunnableConfig, ensure_config

from aidev_agent.config import settings

CODE_CC_MAX_LENGTH = 1024 * 31
session = requests.Session()
_logger = getLogger(__name__)


class CodeCCContentCheckMixIn(BaseChatModel):
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.check_content(messages)
        return super()._generate(messages, stop, run_manager, **kwargs)

    def stream(
        self,
        input: LanguageModelInput,
        config: Optional[RunnableConfig] = None,
        *,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Iterator[BaseMessageChunk]:
        _ = ensure_config(config)
        messages = self._convert_input(input).to_messages()
        self.check_content(messages)
        return super().stream(input, config, stop=stop, **kwargs)

    def request_for_codecc(self, payload: dict):
        """访问Codecc进行敏感词检测"""
        headers = {"Content-Type": "application/json"}
        t1 = time.time()
        resp = session.request(
            "POST", settings.CONTENT_CHECK_CODECC_ENDPOINT, headers=headers, json=payload, timeout=10
        )
        total = time.time() - t1
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            _logger.error(traceback.format_exc())
            raise RuntimeError("敏感信息检查失败")

        info = resp.json()
        _logger.info(f"payload: {payload} | response: {info}, total_time: {total} (s)")
        if info.get("data", {}).get("defectList", ""):
            defectList = info["data"]["defectList"]
            raise RuntimeError(f"提交的内容包含敏感信息: {defectList}")
        return resp

    def check_content(self, messages: List[BaseMessage], **kwargs):
        if not hasattr(settings, "CONTENT_CHECK_CODECC_ENDPOINT"):
            return
        converted_messages = []
        for message in messages:
            converted_messages.append(convert_message_to_dict(message))
        contents = " ".join(
            each["content"]
            for each in converted_messages
            if each.get("content", "") and isinstance(each["content"], str)
        )
        userId = f"txuser{randint(100, 999)}"  # 用随机用户提高并发量
        tasks = []
        pool = ThreadPoolExecutor(4)
        try:
            for idx in range(0, len(contents), CODE_CC_MAX_LENGTH):
                payload = {
                    "bk_app_code": settings.CONTENT_CHECK_CODE,
                    "bk_app_secret": settings.CONTENT_CHECK_SECRET,
                    "userId": userId,
                    "content": contents[idx : idx + CODE_CC_MAX_LENGTH],
                    "checkerSets": [],
                }
                tasks.append(pool.submit(self.request_for_codecc, payload))
            done, _ = wait(tasks, return_when=FIRST_EXCEPTION)
            for each in done:
                each.result()
        finally:
            pool.shutdown(False)
