# -*- coding: utf-8 -*-
from unittest.mock import Mock, patch

from aidev_agent.api import SSMApi


class TestSSMClient:
    """SSM客户端基础测试"""

    @patch("aidev_agent.api.SSMApi.get_client")
    def test_ssm_operations_exist(self, mock_get_client):
        """测试SSM操作是否正确绑定"""
        # Mock 客户端实例
        mock_client = Mock()
        mock_client.create_access_token = Mock()
        mock_client.refresh_access_token = Mock()
        mock_client.verify_access_token = Mock()
        mock_get_client.return_value = mock_client

        client = SSMApi.get_client()

        assert hasattr(client, "create_access_token")
        assert hasattr(client, "refresh_access_token")
        assert hasattr(client, "verify_access_token")

    @patch("aidev_agent.api.SSMApi.get_client")
    def test_create_client_access_token(self, mock_get_client):
        """测试创建应用态token"""
        mock_client = Mock()
        mock_client.create_access_token.return_value = {"code": 0, "data": {"access_token": "test_token"}}
        mock_get_client.return_value = mock_client

        client = SSMApi.get_client()
        response = client.create_access_token({"grant_type": "client_credentials", "id_provider": "client"})

        assert response["data"]["access_token"] == "test_token"
        mock_client.create_access_token.assert_called_once()

    @patch("aidev_agent.api.SSMApi.get_client")
    def test_create_user_access_token(self, mock_get_client):
        """测试创建用户态token"""
        mock_client = Mock()
        mock_client.create_access_token.return_value = {"code": 0, "data": {"access_token": "user_token"}}
        mock_get_client.return_value = mock_client

        client = SSMApi.get_client()
        response = client.create_access_token(
            {"grant_type": "authorization_code", "id_provider": "bk_login", "bk_token": "user_bk_token"}
        )

        assert response["data"]["access_token"] == "user_token"

    @patch("aidev_agent.api.SSMApi.get_client")
    def test_verify_access_token(self, mock_get_client):
        """测试校验token"""
        mock_client = Mock()
        mock_client.verify_access_token.return_value = {"code": 0, "data": {"username": "test_user"}}
        mock_get_client.return_value = mock_client

        client = SSMApi.get_client()
        response = client.verify_access_token({"access_token": "test_token"})

        assert response["data"]["username"] == "test_user"

    @patch("aidev_agent.api.SSMApi.get_client")
    def test_refresh_access_token(self, mock_get_client):
        """测试刷新token"""
        mock_client = Mock()
        mock_client.refresh_access_token.return_value = {"code": 0, "data": {"access_token": "new_token"}}
        mock_get_client.return_value = mock_client

        client = SSMApi.get_client()
        response = client.refresh_access_token({"refresh_token": "old_token"})

        assert response["data"]["access_token"] == "new_token"
