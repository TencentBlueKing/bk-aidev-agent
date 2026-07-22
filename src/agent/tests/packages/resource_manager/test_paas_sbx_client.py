"""``BaseResourceManager.get_paas_sbx_client`` 契约测试。

覆盖：
- 应用凭证路径（有 app_code + app_secret）→ 走 ``BkPaaSSandboxApi.get_client``
- 用户名兜底路径（无 app_code）→ 走 ``BkPaaSSandboxApi.get_client_by_username``
- ``access_token`` / ``bk_username`` 透传到 ``update_bkapi_authorization``
- 前端直调路径的 ``bk_ticket_key`` + ``bk_ticket_value`` 透传到 ``update_bkapi_authorization``
- 两个 ticket 字段任一缺失时不注入（避免污染 auth 头）
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aidev_agent.packages.resource_manager.agent import AgentResourceManager


@pytest.fixture()
def rm() -> AgentResourceManager:
    return AgentResourceManager(app_code="test-app", app_secret="test-secret")


@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock(name="paas_sbx_client")


@pytest.fixture(autouse=True)
def _patch_bkapi(mock_client, monkeypatch):
    """把 BkPaaSSandboxApi.get_client / get_client_by_username 打成 mock，返回同一个 client。"""
    from aidev_agent.packages.resource_manager import base as base_mod

    get_client = MagicMock(return_value=mock_client)
    get_client_by_username = MagicMock(return_value=mock_client)
    monkeypatch.setattr(base_mod.BkPaaSSandboxApi, "get_client", get_client)
    monkeypatch.setattr(base_mod.BkPaaSSandboxApi, "get_client_by_username", get_client_by_username)
    return {"get_client": get_client, "get_client_by_username": get_client_by_username}


class TestAppCredentialsPath:
    def test_app_credentials_prefer_get_client(self, rm, _patch_bkapi):
        """有 app_code + app_secret：走 get_client(app_code=..., app_secret=...)"""
        rm.get_paas_sbx_client(
            {"app_code": "a1", "app_secret": "s1", "executor": "alice"}
        )
        _patch_bkapi["get_client"].assert_called_once_with(app_code="a1", app_secret="s1")
        _patch_bkapi["get_client_by_username"].assert_not_called()

    def test_username_fallback_when_no_app_code(self, rm, _patch_bkapi):
        """无 app_code 或无 app_secret：走 get_client_by_username(bk_username)"""
        rm.get_paas_sbx_client({"executor": "bob"})
        _patch_bkapi["get_client_by_username"].assert_called_once_with("bob")
        _patch_bkapi["get_client"].assert_not_called()


class TestAuthorizationInjection:
    def test_access_token_and_username_forwarded(self, rm, mock_client):
        """access_token + executor 透传到 update_bkapi_authorization"""
        rm.get_paas_sbx_client(
            {"app_code": "a1", "app_secret": "s1", "executor": "alice", "access_token": "tok-abc"}
        )
        mock_client.update_bkapi_authorization.assert_called_once_with(
            access_token="tok-abc", bk_username="alice"
        )

    def test_empty_access_token_becomes_none(self, rm, mock_client):
        """空 access_token 传 None（避免下游把空串当有效 token）"""
        rm.get_paas_sbx_client(
            {"app_code": "a1", "app_secret": "s1", "executor": "alice"}
        )
        call_kwargs = mock_client.update_bkapi_authorization.call_args.kwargs
        assert call_kwargs["access_token"] is None
        assert call_kwargs["bk_username"] == "alice"

    def test_bk_ticket_key_and_value_forwarded(self, rm, mock_client):
        """前端直调路径：bk_ticket_key + bk_ticket_value 透传"""
        rm.get_paas_sbx_client(
            {
                "app_code": "a1",
                "app_secret": "s1",
                "executor": "alice",
                "bk_ticket_key": "bk_ticket",
                "bk_ticket_value": "ticket-xyz",
            }
        )
        mock_client.update_bkapi_authorization.assert_called_once_with(
            access_token=None, bk_username="alice", bk_ticket="ticket-xyz"
        )

    def test_bk_token_key_forwarded_for_open_env(self, rm, mock_client):
        """外部环境：bk_ticket_key='bk_token' 透传"""
        rm.get_paas_sbx_client(
            {
                "app_code": "a1",
                "app_secret": "s1",
                "executor": "alice",
                "bk_ticket_key": "bk_token",
                "bk_ticket_value": "token-xyz",
            }
        )
        call_kwargs = mock_client.update_bkapi_authorization.call_args.kwargs
        assert call_kwargs.get("bk_token") == "token-xyz"
        # 确保没有错误地把 bk_ticket 键也塞进去
        assert "bk_ticket" not in call_kwargs

    def test_bk_ticket_not_injected_when_value_missing(self, rm, mock_client):
        """key 有值 value 为空 → 不注入 ticket 字段（避免污染 auth 头）"""
        rm.get_paas_sbx_client(
            {
                "app_code": "a1",
                "app_secret": "s1",
                "executor": "alice",
                "bk_ticket_key": "bk_ticket",
                "bk_ticket_value": "",
            }
        )
        call_kwargs = mock_client.update_bkapi_authorization.call_args.kwargs
        assert "bk_ticket" not in call_kwargs
        assert "bk_token" not in call_kwargs

    def test_bk_ticket_not_injected_when_key_missing(self, rm, mock_client):
        """value 有值 key 为空 → 不注入（防御性；正常调用不会出现此形态）"""
        rm.get_paas_sbx_client(
            {
                "app_code": "a1",
                "app_secret": "s1",
                "executor": "alice",
                "bk_ticket_key": "",
                "bk_ticket_value": "ticket-xyz",
            }
        )
        call_kwargs = mock_client.update_bkapi_authorization.call_args.kwargs
        assert "bk_ticket" not in call_kwargs
        assert "bk_token" not in call_kwargs

    def test_backward_compatible_no_ticket_fields(self, rm, mock_client):
        """向后兼容：不传 ticket 字段 → 只带 access_token/bk_username"""
        rm.get_paas_sbx_client(
            {"app_code": "a1", "app_secret": "s1", "executor": "alice", "access_token": "tok"}
        )
        # 确保只有 access_token 和 bk_username 两个键
        call_kwargs = mock_client.update_bkapi_authorization.call_args.kwargs
        assert set(call_kwargs.keys()) == {"access_token", "bk_username"}
