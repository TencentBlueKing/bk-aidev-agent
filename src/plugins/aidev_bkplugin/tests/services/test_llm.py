# -*- coding: utf-8 -*-
"""LLMService 单测：调平台 app/v1/llms 网关接口 + llm 空间授权校验。"""

from unittest.mock import patch


class TestLLMServiceListLLMs:
    """list_llms 透传查询参数并抽取 data。"""

    def test_calls_platform_api_with_params_and_user_header(self):
        from aidev_bkplugin.services.llm import LLMService

        with patch("aidev_bkplugin.services.llm.resource_manager") as rm:
            client = rm.return_value.get_client.return_value
            client.api.list_app_v1_llms.return_value = {"data": [{"llm_code": "gpt-4"}]}
            result = LLMService.list_llms(
                username="alice", llm_type="chat.completion", supports="tools,vision", fuzzy="gpt"
            )

        assert result == [{"llm_code": "gpt-4"}]
        client.api.list_app_v1_llms.assert_called_once_with(
            params={"llm_type": "chat.completion", "supports": "tools,vision", "fuzzy": "gpt"},
            headers={"X-BKAIDEV-USER": "alice"},
        )

    def test_omits_empty_params_and_header_when_username_blank(self):
        from aidev_bkplugin.services.llm import LLMService

        with patch("aidev_bkplugin.services.llm.resource_manager") as rm:
            client = rm.return_value.get_client.return_value
            client.api.list_app_v1_llms.return_value = {"data": []}
            LLMService.list_llms(username="")

        client.api.list_app_v1_llms.assert_called_once_with(params={}, headers={})

    def test_returns_empty_list_when_data_missing(self):
        from aidev_bkplugin.services.llm import LLMService

        with patch("aidev_bkplugin.services.llm.resource_manager") as rm:
            client = rm.return_value.get_client.return_value
            client.api.list_app_v1_llms.return_value = {}
            assert LLMService.list_llms(username="alice") == []


class TestLLMServiceAccessible:
    """is_llm_accessible：llm_code 为空放行；非空时按空间可用列表校验。"""

    def test_blank_llm_code_passes(self):
        from aidev_bkplugin.services.llm import LLMService

        assert LLMService.is_llm_accessible(username="alice", llm_code="") is True

    def test_llm_in_list_returns_true(self):
        from aidev_bkplugin.services.llm import LLMService

        with patch.object(LLMService, "list_llms", return_value=[{"llm_code": "gpt-4"}, {"llm_code": "claude"}]):
            assert LLMService.is_llm_accessible(username="alice", llm_code="gpt-4") is True

    def test_llm_not_in_list_returns_false(self):
        from aidev_bkplugin.services.llm import LLMService

        with patch.object(LLMService, "list_llms", return_value=[{"llm_code": "gpt-4"}]):
            assert LLMService.is_llm_accessible(username="alice", llm_code="unknown") is False
