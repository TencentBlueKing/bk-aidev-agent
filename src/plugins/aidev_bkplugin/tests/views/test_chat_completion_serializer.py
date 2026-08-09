# -*- coding: utf-8 -*-
"""ChatCompletionRequestSerializer 校验路径回归测试。

覆盖：
- 主校验：input/chat_history/session_code/thread_id 至少一项必须存在；chat_history 元素必含 role/content。
- execute_kwargs：默认 stream=False、显式 stream/version 透传。
- agent_type：完全由 ``AgentConfigFetcher.get_info()`` 决定，不接受用户输入。
- thread_id：显式 > execute_kwargs.thread_id > uuid 兜底（仅当 session_code 也为空时）。
"""

import uuid
from unittest.mock import patch

import pytest
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_bkplugin.serializers.chat_completion import ChatCompletionRequestSerializer
from rest_framework.exceptions import ValidationError


@pytest.fixture(autouse=True)
def _stub_build_execute_kwargs():
    """build_execute_kwargs 在生产环境会读 OTel/django settings；测试中只关心透传与默认。"""
    with patch("aidev_bkplugin.serializers.chat_completion.build_execute_kwargs") as m:
        m.side_effect = lambda value, username=None: ExecuteKwargs(**value)
        yield m


@pytest.fixture(autouse=True)
def _stub_agent_config_fetcher():
    """``AgentConfigFetcher.get_info`` 走远程 IO + Django cache；测试默认返回 agent_type='common'。

    ``AgentConfigFetcher`` 是 classmethod 风格，patch 类后直接对 ``get_info`` 配置 return_value；
    单测可断言 ``mock_class.get_info.assert_called_once_with(username=, version=)``。
    """
    with patch("aidev_bkplugin.serializers.chat_completion.AgentConfigFetcher") as mock_class:
        mock_class.get_info.return_value = {"agent_type": "common"}
        yield mock_class


class TestChatCompletionRequestSerializerValidation:
    """validate() 主路径与字段约束。"""

    def _validated(self, payload: dict, username: str = "tester") -> dict:
        s = ChatCompletionRequestSerializer(data=payload, context={"username": username})
        s.is_valid(raise_exception=True)
        return s.validated_data

    def test_rejects_when_input_history_session_thread_all_empty(self):
        s = ChatCompletionRequestSerializer(data={}, context={"username": "u"})
        with pytest.raises(ValidationError):
            s.is_valid(raise_exception=True)

    @pytest.mark.parametrize(
        "payload",
        [
            {"input": "hi"},
            {"chat_history": [{"role": "user", "content": "hi"}]},
            {"session_code": "s-1"},
            {"thread_id": "t-1"},
        ],
    )
    def test_accepts_when_any_anchor_field_present(self, payload):
        data = self._validated(payload)
        assert isinstance(data["execute_kwargs"], ExecuteKwargs)

    @pytest.mark.parametrize(
        "bad_item",
        [{"role": "user"}, {"content": "x"}, {}],
    )
    def test_chat_history_item_must_have_role_and_content(self, bad_item):
        s = ChatCompletionRequestSerializer(
            data={"input": "hi", "chat_history": [bad_item]},
            context={"username": "u"},
        )
        with pytest.raises(ValidationError):
            s.is_valid(raise_exception=True)


class TestChatCompletionRequestSerializerExecuteKwargs:
    """execute_kwargs 字段：默认 stream=False、直接返回 ExecuteKwargs。"""

    def test_default_stream_is_false_when_omitted(self):
        s = ChatCompletionRequestSerializer(data={"input": "hi"}, context={"username": "u"})
        s.is_valid(raise_exception=True)
        ek = s.validated_data["execute_kwargs"]
        assert isinstance(ek, ExecuteKwargs)
        assert ek.stream is False

    def test_stream_true_passes_through(self):
        s = ChatCompletionRequestSerializer(
            data={"input": "hi", "execute_kwargs": {"stream": True}},
            context={"username": "u"},
        )
        s.is_valid(raise_exception=True)
        assert s.validated_data["execute_kwargs"].stream is True

    def test_version_passes_through(self):
        s = ChatCompletionRequestSerializer(
            data={"input": "hi", "execute_kwargs": {"version": "v2"}},
            context={"username": "u"},
        )
        s.is_valid(raise_exception=True)
        assert s.validated_data["execute_kwargs"].version == "v2"

    def test_stream_mode_defaults_to_start_and_attach_passes_through(self):
        default = ChatCompletionRequestSerializer(data={"input": "hi"}, context={"username": "u"})
        default.is_valid(raise_exception=True)
        assert default.validated_data["execute_kwargs"].stream_mode == "start"

        attach = ChatCompletionRequestSerializer(
            data={"session_code": "s-1", "execute_kwargs": {"stream": True, "stream_mode": "attach"}},
            context={"username": "u"},
        )
        attach.is_valid(raise_exception=True)
        assert attach.validated_data["execute_kwargs"].stream_mode == "attach"


class TestChatCompletionRequestSerializerCompatFields:
    """flow / poll / 兼容字段透传校验。"""

    def test_flow_payload_passes_validation(self, _stub_agent_config_fetcher):
        _stub_agent_config_fetcher.get_info.return_value = {"agent_type": "flow"}
        payload = {
            "input": "go",
            "task_id": "task-1",
            "flow_start_params": {"k": "v"},
            "poll_interval": 0.5,
            "poll_timeout": 30.0,
        }
        s = ChatCompletionRequestSerializer(data=payload, context={"username": "u"})
        s.is_valid(raise_exception=True)
        d = s.validated_data
        assert d["agent_type"] == "flow"
        assert d["task_id"] == "task-1"
        assert d["flow_start_params"] == {"k": "v"}
        assert d["poll_interval"] == 0.5
        assert d["poll_timeout"] == 30.0

    def test_chat_prompts_legacy_field_is_silently_ignored(self):
        # chat_prompts 已下线，仅靠 chat_history 满足校验；不会因传入 chat_prompts 而报错或被消费。
        payload = {"chat_prompts": [{"role": "user", "content": "x"}]}
        s = ChatCompletionRequestSerializer(data=payload, context={"username": "u"})
        with pytest.raises(ValidationError):
            s.is_valid(raise_exception=True)


class TestChatCompletionRequestSerializerAgentTypeFromAgentInfo:
    """agent_type 完全由 ``AgentConfigFetcher.get_info()`` 决定，不接受用户输入。"""

    def _validated(self, payload: dict, context: dict | None = None) -> dict:
        s = ChatCompletionRequestSerializer(data=payload, context=context or {"username": "u"})
        s.is_valid(raise_exception=True)
        return s.validated_data

    def test_agent_type_taken_from_agent_info(self, _stub_agent_config_fetcher):
        _stub_agent_config_fetcher.get_info.return_value = {"agent_type": "from-config"}
        data = self._validated({"input": "hi"})
        assert data["agent_type"] == "from-config"

    def test_user_supplied_agent_type_is_ignored(self, _stub_agent_config_fetcher):
        # 用户在请求体中传入 agent_type 不会生效（serializer 没有该字段定义，会被 DRF 忽略）。
        _stub_agent_config_fetcher.get_info.return_value = {"agent_type": "from-config"}
        data = self._validated({"input": "hi", "agent_type": "user-supplied"})
        assert data["agent_type"] == "from-config"

    def test_agent_type_defaults_to_empty_when_agent_info_missing_field(self, _stub_agent_config_fetcher):
        _stub_agent_config_fetcher.get_info.return_value = {}
        data = self._validated({"input": "hi"})
        assert data["agent_type"] == ""

    def test_get_info_called_with_username_and_version(self, _stub_agent_config_fetcher):
        self._validated(
            {"input": "hi", "execute_kwargs": {"version": "v2"}},
            context={"username": "alice"},
        )
        _stub_agent_config_fetcher.get_info.assert_called_once_with(username="alice", version="v2")

    def test_get_info_called_with_none_version_by_default(self, _stub_agent_config_fetcher):
        self._validated({"input": "hi"}, context={"username": "alice"})
        _stub_agent_config_fetcher.get_info.assert_called_once_with(username="alice", version=None)


class TestChatCompletionRequestSerializerThreadIdFallback:
    """thread_id 合并规则：显式 > execute_kwargs.thread_id > uuid 兜底。"""

    def _validated(self, payload: dict) -> dict:
        s = ChatCompletionRequestSerializer(data=payload, context={"username": "u"})
        s.is_valid(raise_exception=True)
        return s.validated_data

    def test_thread_id_uses_explicit_value_when_provided(self):
        data = self._validated({"input": "hi", "thread_id": "t-explicit"})
        assert data["thread_id"] == "t-explicit"

    def test_thread_id_falls_back_to_execute_kwargs_thread_id(self):
        data = self._validated({"input": "hi", "execute_kwargs": {"thread_id": "t-from-ek"}})
        assert data["thread_id"] == "t-from-ek"

    def test_thread_id_auto_uuid_when_no_thread_id_no_session_code(self):
        data = self._validated({"input": "hi"})
        assert data["thread_id"]
        uuid.UUID(data["thread_id"])

    def test_thread_id_not_generated_when_session_code_present(self):
        data = self._validated({"session_code": "s-1"})
        assert data["thread_id"] == ""
