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

import functools
from base64 import b64encode
from pathlib import PosixPath
from random import randint
from typing import List, cast

from langchain_core.stores import ByteStore
from langchain_core.tools import StructuredTool, ToolException

from aidev_agent.core.utils.local import request_local
from aidev_agent.packages.langchain.exceptions import TooMuchToolException

IMAGE_SUFFIXES = ("jpg", "jpeg", "png", "gif")


def exception_to_tool_exception(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as err:
            raise ToolException(str(err))

    return inner


class ToolErrorHandler:
    """用于处理工具调用失败的情况
    当工具调用失败太多,抛出调用失败的异常;
    针对同一个线程
    """

    max_retry: int = 3

    def __init__(self, _id: str = ""):
        self._id = _id if _id else str(randint(1, 9999))

    def __call__(self, exc: ToolException) -> str:
        local_key = f"{self._id}_tool_try"
        tool_try = getattr(request_local, local_key, 1)
        tool_try += 1
        if tool_try > self.max_retry:
            delattr(request_local, local_key)
            raise TooMuchToolException()
        setattr(request_local, local_key, tool_try)
        return f"exception when calling tool, exception: {exc}"


@exception_to_tool_exception
def _add_image_to_chat_context(file_names: List[str]) -> str:
    user_store = getattr(request_local, "current_user_store", {})
    file_store = cast(ByteStore, user_store.get("file_store"))
    content = file_store.mget(file_names)
    if not content:
        return "No image"
    user_store["image"] = {
        file_names[n]: b64encode(c).decode()
        for n, c in enumerate(content)
        if PosixPath(file_names[n]).suffix[1:] in IMAGE_SUFFIXES
    }
    setattr(request_local, "current_user_store", user_store)
    return (
        f"Image {file_names} has been already added to the context. Never add it again. Please based on the image for"
        " reference."
    )


add_image_to_chat_context = StructuredTool.from_function(
    _add_image_to_chat_context,
    name="add_image_to_chat_context",
    description=(
        "Add uploaded image to the chat context by file names. "
        "After execute this tools successfully, you will get the image content from the chat context."
    ),
    metadata={"tool_name": "添加图片"},
    handle_tool_error=ToolErrorHandler("add_image_to_chat_context"),
)
