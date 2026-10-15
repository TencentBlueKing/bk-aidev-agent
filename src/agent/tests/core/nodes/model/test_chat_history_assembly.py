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
            model_name="test-model",
            agent_info=None,
            generating_keyword=None,
            files=files,
            support_vision=True,
        )
        assert files == [{"file_name": "https://example.com/files/upload_file.jpeg", "file_size": 100}]

    def test_user_image_inlines_when_model_supports_vision(self):
        """本轮图片 + 多模态主模型：直接用主模型的多模态能力，走 image_url。"""
        chat_prompt = ChatPrompt(
            id="img2",
            role=PromptRole.USER_IMAGE.value,
            content="![图](https://example.com/files/upload_file.jpeg)",
        )
        messages = convert_chat_history_to_messages(
            [chat_prompt],
            model_context_options=None,
            model_name="test-model",
            agent_info=None,
            generating_keyword=None,
            files=[],
            support_vision=True,
        )

        assert messages[0].content == [
            {"type": "image_url", "image_url": {"url": "https://example.com/files/upload_file.jpeg"}}
        ]

    def test_user_image_without_session_path_does_not_suggest_read_image(self):
        """旧 USER_IMAGE 只有外链时不猜测会话路径，避免生成无效 read_image 入参。"""
        chat_prompt = ChatPrompt(
            id="img2",
            role=PromptRole.USER_IMAGE.value,
            content="![图](https://example.com/files/upload_file.jpeg)",
        )
        messages = convert_chat_history_to_messages(
            [chat_prompt],
            model_context_options=None,
            model_name="test-model",
            agent_info=None,
            generating_keyword=None,
            files=[],
            support_vision=False,
        )

        assert messages[0].content[0]["type"] == "text"
        assert "read_image" not in messages[0].content[0]["text"]
        assert "取不到图片路径" in messages[0].content[0]["text"]


class TestImageInlineFollowsVisionOnly:
    """图片处理只看主模型多模态能力，本轮与历史同一判据。"""

    @staticmethod
    def _history():
        # 带 url：装配链跑之前 _refresh_llm_history_image_urls 已经给历史图片重签过，
        # 不带 url 的图片走的是「取不到 url 就降级」那条路，不是这里要验的判据
        return [
            ChatPrompt(
                id="old",
                role=PromptRole.USER.value,
                content=[
                    {
                        "type": "binary",
                        "mime_type": "image/png",
                        "path": "files/old.png",
                        "url": "https://example.test/old.png",
                    }
                ],
            ),
            ChatPrompt(id="answer", role=PromptRole.ASSISTANT.value, content="上一轮回答"),
            ChatPrompt(
                id="now",
                role=PromptRole.USER.value,
                content=[
                    {
                        "type": "binary",
                        "mime_type": "image/png",
                        "path": "files/now.png",
                        "url": "https://example.test/now.png",
                    }
                ],
            ),
        ]

    @staticmethod
    def _convert(chat_history, *, support_vision):
        return convert_chat_history_to_messages(
            chat_history,
            model_context_options=None,
            model_name="test-model",
            agent_info=None,
            generating_keyword=None,
            files=[],
            support_vision=support_vision,
        )

    def test_vision_model_inlines_history_images_too(self):
        """多模态主模型：历史图片同样保留 binary 交给网关内联。

        历史图片若降级成路径文本，而 read_image 未注册（skills / runtime_backend_resolver /
        视觉模型三者缺一即不注册），模型就只剩一句指向不存在工具的提示，历史图片彻底失明。
        """
        history = self._history()
        messages = self._convert(history, support_vision=True)

        assert messages[0].content == history[0].content
        assert messages[2].content == history[2].content

    def test_non_vision_model_degrades_history_and_current_images(self):
        """非多模态主模型：本轮与历史图片一起降级，binary 不会漏到网关变成 image_url。"""
        messages = self._convert(self._history(), support_vision=False)

        for index, path in ((0, "files/old.png"), (2, "files/now.png")):
            assert messages[index].content[0]["type"] == "text"
            assert path in messages[index].content[0]["text"]
            assert f"file://<target_runtime>/$STORAGE_PATH/session/{path}" in messages[index].content[0]["text"]

    def test_non_image_binary_is_passed_through_to_gateway(self):
        """非图片 binary 不在装配链判定，原样透传给网关按原有规则丢弃。"""
        item = {"type": "binary", "mime_type": "text/plain", "path": "files/a.txt"}
        messages = self._convert(
            [ChatPrompt(id="now", role=PromptRole.USER.value, content=[item])],
            support_vision=False,
        )

        assert messages[0].content == [item]

    def test_nested_image_url_is_inlined_with_vision(self):
        """标准 image_url.url 形态与顶层 URL 形态使用同一内联规则。"""
        item = {
            "type": "image_url",
            "path": "files/now.png",
            "image_url": {"url": "https://example.com/files/now.png", "detail": "high"},
        }

        messages = self._convert(
            [ChatPrompt(id="now", role=PromptRole.USER.value, content=[item])],
            support_vision=True,
        )

        assert messages[0].content == [
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/files/now.png", "detail": "high"},
            }
        ]

    def test_nested_image_url_degrades_to_session_path_without_vision(self):
        """标准 image_url.url 形态降级时使用显式会话路径，避免把 HTTP URL 传给 read_image。"""
        item = {
            "type": "image_url",
            "path": "files/now.png",
            "image_url": {"url": "https://example.com/files/now.png"},
        }

        messages = self._convert(
            [ChatPrompt(id="now", role=PromptRole.USER.value, content=[item])],
            support_vision=False,
        )

        text = messages[0].content[0]["text"]
        assert "files/now.png" in text
        assert "file://<target_runtime>/$STORAGE_PATH/session/files/now.png" in text
        assert "https://" not in text

    def test_non_image_url_type_is_passed_through(self):
        """非图片 URL 类型不应被图片守卫拦截或降级。"""
        item = {"type": "audio_url", "audio_url": {"url": "https://example.com/now.mp3"}}

        messages = self._convert(
            [ChatPrompt(id="now", role=PromptRole.USER.value, content=[item])],
            support_vision=False,
        )

        assert messages[0].content == [item]

    def test_external_image_url_does_not_suggest_read_image(self):
        """无法映射到会话 PV 的网络图片不应生成无效 read_image 入参。"""
        item = {"type": "image_url", "image_url": {"url": "https://example.com/now.png"}}

        messages = self._convert(
            [ChatPrompt(id="now", role=PromptRole.USER.value, content=[item])],
            support_vision=False,
        )

        text = messages[0].content[0]["text"]
        assert "read_image" not in text
        assert "取不到图片路径" in text

    def test_image_without_url_or_data_degrades_even_with_vision(self):
        """重签失败摘掉 URL 后，即使主模型多模态也要在装配链降级。

        留给网关兜底就等于「该不该内联」散在两层；而且网关没有降级所需的上下文，
        真发出去就是一条必然 404 的链接。
        """
        messages = self._convert(
            [
                ChatPrompt(
                    id="now",
                    role=PromptRole.USER.value,
                    content=[{"type": "binary", "mime_type": "image/png", "path": "files/now.png"}],
                )
            ],
            support_vision=True,
        )

        assert messages[0].content[0]["type"] == "text"
        assert "files/now.png" in messages[0].content[0]["text"]

    def test_base64_image_stays_inline_with_vision(self):
        """只有 base64 data、没有 url 的图片仍可内联：网关会拼成 data URL。"""
        item = {"type": "binary", "mime_type": "image/png", "data": "Zm9v", "path": "files/now.png"}
        messages = self._convert(
            [ChatPrompt(id="now", role=PromptRole.USER.value, content=[item])],
            support_vision=True,
        )

        assert messages[0].content == [item]

    def test_degraded_text_omits_read_image_without_path(self):
        """连路径都取不到时不提 read_image：没有 path 可传，提示只会让模型去猜一个不存在的路径。"""
        messages = self._convert(
            [
                ChatPrompt(
                    id="now",
                    role=PromptRole.USER.value,
                    content=[{"type": "binary", "mime_type": "image/png"}],
                )
            ],
            support_vision=False,
        )

        text = messages[0].content[0]["text"]
        assert "read_image" not in text
        assert "取不到图片路径" in text


class TestCurrentTurnImageRecognizableGuard:
    """非多模态主模型 + 未配视觉模型：本轮带图报错，历史带图软降级。"""

    @staticmethod
    def _image_prompt(prompt_id, path):
        return ChatPrompt(
            id=prompt_id,
            role=PromptRole.USER.value,
            content=[{"type": "binary", "mime_type": "image/png", "path": path, "url": f"https://example.test/{path}"}],
        )

    @staticmethod
    def _convert(chat_history, *, support_vision=False, vision_model_configured=False):
        return convert_chat_history_to_messages(
            chat_history,
            model_context_options=None,
            model_name="test-model",
            agent_info=None,
            generating_keyword=None,
            files=[],
            support_vision=support_vision,
            vision_model_configured=vision_model_configured,
        )

    def test_raises_when_no_vision_capability_at_all(self):
        """主模型读不了图、read_image 又必定不注册，明确告知换模型而不是让模型答「看不到图」。

        文案要同时点出两个条件与主模型名：少任何一项，管理员都判断不出是模型选错还是
        视觉模型没配，也就不知道该改哪个。
        """
        with pytest.raises(AgentException) as exc_info:
            self._convert([self._image_prompt("now", "files/now.png")])

        message = str(exc_info.value)
        assert "test-model" in message
        assert "不支持图片输入" in message
        assert "FALLBACK_VISION_MODEL" in message

    def test_raises_for_legacy_user_image_role(self):
        """旧 USER_IMAGE 形态与会话上传图片同判据，守卫在角色归一之后执行。"""
        prompt = ChatPrompt(
            id="now",
            role=PromptRole.USER_IMAGE.value,
            content="![图](https://example.com/files/a.jpeg)",
        )
        with pytest.raises(AgentException, match="FALLBACK_VISION_MODEL"):
            self._convert([prompt])

    def test_history_only_image_degrades_instead_of_raising(self):
        """只有历史带图时不报错：老会话不该因为换了个模型就整段卡住。"""
        chat_history = [
            self._image_prompt("old", "files/old.png"),
            ChatPrompt(id="answer", role=PromptRole.ASSISTANT.value, content="上一轮回答"),
            ChatPrompt(id="now", role=PromptRole.USER.value, content="继续"),
        ]

        messages = self._convert(chat_history)

        assert messages[0].content[0]["type"] == "text"
        assert "files/old.png" in messages[0].content[0]["text"]

    def test_no_raise_when_vision_model_configured(self):
        """配了视觉模型：read_image 能识别，降级成路径文本即可。"""
        messages = self._convert([self._image_prompt("now", "files/now.png")], vision_model_configured=True)

        assert messages[0].content[0]["type"] == "text"

    def test_no_raise_when_main_model_supports_vision(self):
        """多模态主模型：图片直接内联，与视觉模型是否配置无关。"""
        messages = self._convert([self._image_prompt("now", "files/now.png")], support_vision=True)

        assert messages[0].content[0]["type"] == "binary"

    def test_no_raise_for_text_only_current_turn(self):
        """本轮不带图：模型组合再受限也不该拦住纯文本提问。"""
        messages = self._convert([ChatPrompt(id="now", role=PromptRole.USER.value, content="纯文本")])

        assert messages[0].content == "纯文本"
