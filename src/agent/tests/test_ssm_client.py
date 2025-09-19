# -*- coding: utf-8 -*-
"""SSM客户端测试文件"""

import json
import time
from unittest.mock import Mock, patch

import responses
from aidev_agent.api.bk_ssm import SSMApi
from aidev_agent.api.ssm_client import SSMClient, TokenInfo


class TestSSMClient:
    """SSM客户端测试类"""

    def setup_method(self):
        """测试前准备"""
        self.base_url = "https://test-ssm.example.com"
        self.app_code = "test_app"
        self.app_secret = "test_secret"
        self.client = SSMClient(
            base_url=self.base_url,
            app_code=self.app_code,
            app_secret=self.app_secret,
        )

    def test_init(self):
        """测试初始化"""
        assert self.client.base_url == self.base_url
        assert self.client.app_code == self.app_code
        assert self.client.app_secret == self.app_secret
        assert self.client.timeout == 15

    def test_headers(self):
        """测试请求头生成"""
        headers = self.client._headers()
        expected_headers = {
            "X-Bk-App-Code": self.app_code,
            "X-Bk-App-Secret": self.app_secret,
            "Content-Type": "application/json",
        }
        assert headers == expected_headers

    def test_cache_key_generation(self):
        """测试缓存key生成"""
        # 应用态
        client_key = self.client._get_cache_key()
        assert client_key == f"{self.app_code}:client"

        # 用户态
        user_key = self.client._get_cache_key("test_user")
        assert user_key == f"{self.app_code}:test_user:user"

    @responses.activate
    def test_get_client_access_token_success(self):
        """测试获取应用态access_token成功"""
        responses.add(
            responses.POST,
            f"{self.base_url}/api/v1/auth/access-tokens",
            json={
                "code": 0,
                "data": {
                    "access_token": "test_client_token",
                    "refresh_token": "test_refresh_token",
                    "expires_in": 43200,
                    "identity": {"app_code": "test_app", "type": "client"},
                },
                "message": "success",
            },
            status=200,
        )

        access_token = self.client.get_client_access_token()

        assert access_token == "test_client_token"

        assert len(responses.calls) == 1
        request_data = responses.calls[0].request.body

        request_json = json.loads(request_data)
        assert request_json["grant_type"] == "client_credentials"
        assert request_json["id_provider"] == "client"

    @responses.activate
    def test_get_user_access_token_success(self):
        """测试获取用户态access_token成功"""

        responses.add(
            responses.POST,
            f"{self.base_url}/api/v1/auth/access-tokens",
            json={
                "code": 0,
                "data": {
                    "access_token": "test_user_token",
                    "refresh_token": "test_refresh_token",
                    "expires_in": 43200,
                    "identity": {"username": "test_user", "user_type": "bkuser"},
                },
                "message": "success",
            },
            status=200,
        )

        username = "test_user"
        bk_token = "test_bk_token"
        access_token = self.client.get_user_access_token(username, bk_token)

        assert access_token == "test_user_token"

        assert len(responses.calls) == 1
        request_data = responses.calls[0].request.body

        request_json = json.loads(request_data)
        assert request_json["grant_type"] == "authorization_code"
        assert request_json["id_provider"] == "bk_login"
        assert request_json["bk_token"] == bk_token

    @responses.activate
    def test_token_caching(self):
        """测试token缓存功能"""

        responses.add(
            responses.POST,
            f"{self.base_url}/api/v1/auth/access-tokens",
            json={
                "code": 0,
                "data": {
                    "access_token": "cached_token",
                    "refresh_token": "test_refresh_token",
                    "expires_in": 43200,
                    "identity": {"app_code": "test_app", "type": "client"},
                },
                "message": "success",
            },
            status=200,
        )

        token1 = self.client.get_client_access_token()
        assert token1 == "cached_token"
        assert len(responses.calls) == 1

        token2 = self.client.get_client_access_token()
        assert token2 == "cached_token"
        assert len(responses.calls) == 1

    @responses.activate
    def test_token_refresh(self):
        """测试token刷新"""
        # 先添加一个即将过期的token到缓存
        cache_key = self.client._get_cache_key()
        expired_token = TokenInfo(
            access_token="expired_token",
            refresh_token="test_refresh_token",
            expires_in=3600,
            created_at=time.time() - 3900,  # 3900秒前创建，已过期
            identity={"app_code": "test_app", "type": "client"},
        )
        self.client._token_cache[cache_key] = expired_token

        responses.add(
            responses.POST,
            f"{self.base_url}/api/v1/auth/access-tokens/refresh",
            json={
                "code": 0,
                "data": {
                    "access_token": "refreshed_token",
                    "refresh_token": "new_refresh_token",
                    "expires_in": 43200,
                    "identity": {"app_code": "test_app", "type": "client"},
                },
                "message": "success",
            },
            status=200,
        )

        token = self.client.get_client_access_token()

        assert token == "refreshed_token"
        assert len(responses.calls) == 1

        request_data = responses.calls[0].request.body

        request_json = json.loads(request_data)
        assert request_json["refresh_token"] == "test_refresh_token"

    @responses.activate
    def test_verify_access_token(self):
        """测试校验access_token"""
        responses.add(
            responses.POST,
            f"{self.base_url}/api/v1/auth/access-tokens/verify",
            json={
                "code": 0,
                "data": {"is_valid": True, "identity": {"username": "test_user", "user_type": "bkuser"}},
                "message": "success",
            },
            status=200,
        )

        result = self.client.verify_access_token("test_token")

        assert result["code"] == 0
        assert result["data"]["is_valid"] is True

    def test_token_info_expiration(self):
        """测试TokenInfo过期检查"""
        # 未过期的token
        valid_token = TokenInfo(
            access_token="valid_token",
            refresh_token="refresh_token",
            expires_in=3600,
            created_at=time.time(),
            identity={},
        )
        assert not valid_token.is_expired

        # 已过期的token
        expired_token = TokenInfo(
            access_token="expired_token",
            refresh_token="refresh_token",
            expires_in=3600,
            created_at=time.time() - 4000,  # 4000秒前创建
            identity={},
        )
        assert expired_token.is_expired

    def test_cache_management(self):
        """测试缓存管理"""
        # 添加一些缓存
        self.client._token_cache["key1"] = Mock()
        self.client._token_cache["key2"] = Mock()

        # 清理特定用户缓存
        user_key = self.client._get_cache_key("test_user")
        self.client._token_cache[user_key] = Mock()

        self.client.clear_cache("test_user")
        assert user_key not in self.client._token_cache
        assert "key1" in self.client._token_cache  # 其他缓存不受影响

        # 清理所有缓存
        self.client.clear_cache()
        assert len(self.client._token_cache) == 0


class TestSSMApi:
    """SSM API工厂类测试"""

    def test_get_user_client(self):
        """测试获取用户态客户端"""
        # 创建模拟request对象
        mock_request = Mock()
        mock_request.username = "test_user"
        mock_request.user = Mock()
        mock_request.user.username = "test_user"
        mock_request.META = {"HTTP_BK_TOKEN": "test_bk_token"}
        mock_request.COOKIES = {}

        with patch("aidev_agent.api.bk_ssm.SSMClient") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # 模拟配置以避免初始化错误
            with patch("aidev_agent.api.ssm_client.settings") as mock_settings:
                mock_settings.APP_CODE = "test_app"
                mock_settings.SECRET_KEY = "test_secret"
                mock_settings.BK_SSM_ENDPOINT = "https://test-ssm.example.com"

                client = SSMApi.get_user_client(mock_request)

                assert client == mock_client
                mock_client_class.assert_called_once()
                # 验证设置了request上下文
                assert mock_client._request_context == {
                    "username": "test_user",
                    "bk_token": "test_bk_token",
                    "is_user_mode": True,
                }

    def test_get_client_client(self):
        """测试获取应用态客户端"""
        with patch("aidev_agent.api.bk_ssm.SSMClient") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            client = SSMApi.get_client_client()

            assert client == mock_client
            mock_client_class.assert_called_once()

    def test_get_client_by_request(self):
        """测试通过request获取客户端"""
        # 测试无用户信息的情况（应用态）
        mock_request = Mock()
        mock_request.username = None
        mock_request.user = Mock()
        mock_request.user.username = None
        mock_request.META = {}
        mock_request.COOKIES = {}

        with patch("aidev_agent.api.bk_ssm.SSMApi.get_client_client") as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            client = SSMApi.get_client_by_request(mock_request)

            assert client == mock_client
            mock_get_client.assert_called_once()

    def test_get_client_by_request_with_user(self):
        """测试通过request获取用户态客户端"""
        # 测试有用户信息的情况（用户态）
        mock_request = Mock()
        mock_request.username = "test_user"
        mock_request.user = Mock()
        mock_request.user.username = "test_user"
        mock_request.META = {"HTTP_BK_TOKEN": "test_bk_token"}
        mock_request.COOKIES = {}

        with patch("aidev_agent.api.bk_ssm.SSMApi.get_user_client") as mock_get_user:
            mock_client = Mock()
            mock_get_user.return_value = mock_client

            client = SSMApi.get_client_by_request(mock_request)

            assert client == mock_client
            mock_get_user.assert_called_once_with(mock_request)


class TestSSMIntegration:
    """SSM集成测试"""

    @responses.activate
    def test_complete_workflow(self):
        """测试完整的工作流程"""
        # 应用态token创建
        responses.add(
            responses.POST,
            "https://test-ssm.example.com/api/v1/auth/access-tokens",
            json={
                "code": 0,
                "data": {
                    "access_token": "workflow_token",
                    "refresh_token": "workflow_refresh",
                    "expires_in": 43200,
                    "identity": {"app_code": "test_app", "type": "client"},
                },
                "message": "success",
            },
            status=200,
        )

        responses.add(
            responses.POST,
            "https://test-ssm.example.com/api/v1/auth/access-tokens/verify",
            json={
                "code": 0,
                "data": {"is_valid": True, "identity": {"app_code": "test_app", "type": "client"}},
                "message": "success",
            },
            status=200,
        )

        # 创建客户端
        client = SSMClient(
            base_url="https://test-ssm.example.com",
            app_code="test_app",
            app_secret="test_secret",
        )

        # 获取应用态token
        access_token = client.get_client_access_token()
        assert access_token == "workflow_token"

        # 验证token
        verify_result = client.verify_access_token(access_token)
        assert verify_result["code"] == 0
        assert verify_result["data"]["is_valid"] is True

        # 检查缓存
        cache_info = client.get_cache_info()
        assert len(cache_info) == 1

        # 清理缓存
        client.clear_cache()
        cache_info = client.get_cache_info()
        assert len(cache_info) == 0
