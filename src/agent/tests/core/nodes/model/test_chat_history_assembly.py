# -*- coding: utf-8 -*-
"""Tests for aidev_agent.core.nodes.model.chat_history_assembly（messages 历史装配链迁移验证）。

锁定从 ChatCompletionAgent 抽取后保持不变的行为：USER_IMAGE 转换对调用方 files 列表的
原地 append 副作用（传引用语义）与视觉支持守卫。其余链行为由 tests/services/test_chat.py
与快照三件套既有断言锁定（调用路径改向，断言零变化）。
"""

import pytest
from aidev_agent.core.nodes.model.chat_history_assembly import convert_chat_history_to_messages
from aidev_agent.enums import PromptRole
from aidev_agent.exceptions import AgentException
from aidev_agent.pydantic_models import ChatPrompt


class TestFilesAppendSideEffect:
    """USER_IMAGE 转换的 files 传引用 append 副作用与 vision 守卫。"""

    def test_user_image_appends_to_files_list(self):
        chat_prompt = ChatPrompt(
            id="img1",
            role=PromptRole.USER_IMAGE.value,
            content="![图](https://example.com/files/upload_file.jpeg)",
        )
        files: list[dict] = []
        convert_chat_history_to_messages(
            [chat_prompt],
            model_context_options=None,
            support_vision=True,
            model_name="test-model",
            agent_info=None,
            generating_keyword=None,
            files=files,
        )
        assert files == [{"file_name": "https://example.com/files/upload_file.jpeg", "file_size": 100}]

    def test_user_image_without_vision_support_raises(self):
        chat_prompt = ChatPrompt(
            id="img2",
            role=PromptRole.USER_IMAGE.value,
            content="![图](https://example.com/files/upload_file.jpeg)",
        )
        with pytest.raises(AgentException):
            convert_chat_history_to_messages(
                [chat_prompt],
                model_context_options=None,
                support_vision=False,
                model_name="test-model",
                agent_info=None,
                generating_keyword=None,
                files=[],
            )
