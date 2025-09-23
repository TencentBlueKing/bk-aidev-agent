# -*- coding: utf-8 -*-
import json
import time
from unittest.mock import Mock

import pytest
import responses
from aidev_agent.api.ssm_client import (
    SSMClient,
    SSMException,
    TokenInfo,
    get_ssm_client,
)


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

    def test_basic_functionality(self):
        """测试基础功能：初始化、请求头、缓存key生成"""
        # 测试初始化
        assert self.client.base_url == self.base_url
        assert self.client.app_code == self.app_code
        assert self.client.app_secret == self.app_secret
        assert self.client.timeout == 15

        # 测试请求头生成
        headers = self.client._headers()
        expected_headers = {
            "X-Bk-App-Code": self.app_code,
            "X-Bk-App-Secret": self.app_secret,
            "Content-Type": "application/json",
        }
        assert headers == expected_headers

        # 测试缓存key生成
        client_key = self.client._get_cache_key()
        assert client_key == f"{self.app_code}:client"
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

    @responses.activate
    def test_django_request_integration(self):
        """测试Django request集成功能：上下文设置、信息提取、优先级处理"""
        responses.add(
            responses.POST,
            f"{self.base_url}/api/v1/auth/access-tokens",
            json={
                "code": 0,
                "data": {
                    "access_token": "request_token",
                    "refresh_token": "refresh_token",
                    "expires_in": 43200,
                    "identity": {"username": "request_user", "user_type": "bkuser"},
                },
                "message": "success",
            },
            status=200,
        )

        # 1. 测试基本的request上下文设置
        request_mock = Mock()
        request_mock.user.username = "test_user"
        request_mock.META = {"HTTP_AIDEV_TICKET": "test_ticket"}
        request_mock.COOKIES = {}

        self.client.set_request_context(request_mock)
        assert self.client._request_context["is_user_mode"] is True
        assert self.client._request_context["username"] == "test_user"
        assert self.client._request_context["bk_token"] == "test_ticket"

        # 2. 测试手动参数覆盖request中的参数（优先级）
        self.client.set_request_context(request=request_mock, username="manual_user", bk_token="manual_token")
        assert self.client._request_context["username"] == "manual_user"
        assert self.client._request_context["bk_token"] == "manual_token"

        # 3. 测试bk_token提取的优先级：META > COOKIES
        request_mock.META = {"HTTP_AIDEV_TICKET": "meta_token"}
        request_mock.COOKIES = {"bk_token": "cookie_token"}
        token = self.client._extract_bk_token_from_request(request_mock)
        assert token == "meta_token"

        request_mock.META = {}
        token = self.client._extract_bk_token_from_request(request_mock)
        assert token == "cookie_token"

        # 4. 测试用户名提取：request.user > cookies
        request_mock = Mock()
        request_mock.user.username = "django_user"
        request_mock.COOKIES = {"bk_uid": "cookie_user"}
        username = self.client._extract_username_from_request(request_mock)
        assert username == "django_user"

        request_mock.user = None
        username = self.client._extract_username_from_request(request_mock)
        assert username == "cookie_user"

        # 5. 测试通过request获取token
        request_mock = Mock()
        request_mock.user.username = "request_user"
        request_mock.META = {"HTTP_AIDEV_TICKET": "request_bk_token"}
        request_mock.COOKIES = {}

        access_token = self.client.get_user_access_token(request=request_mock)
        assert access_token == "request_token"

        access_token = self.client.get_access_token_for_request(request_mock)
        assert access_token == "request_token"

        # 6. 测试异常处理
        with pytest.raises(Exception, match="request参数不能为空"):
            self.client.get_access_token_for_request(None)

    def test_configuration_and_initialization(self):
        """测试配置验证和初始化逻辑"""
        from unittest.mock import patch

        # 测试缺少必需参数时的异常
        with pytest.raises(SSMException, match="app_code 和 app_secret 必须提供"):
            SSMClient(base_url="https://test.example.com", app_code="", app_secret="test_secret")

        with pytest.raises(SSMException, match="app_code 和 app_secret 必须提供"):
            SSMClient(base_url="https://test.example.com", app_code="test_app", app_secret="")

        with pytest.raises(SSMException, match="SSM endpoint 未配置"):
            SSMClient(base_url="", app_code="test_app", app_secret="test_secret")

        # 测试端点选择逻辑
        # 1. 优先使用自定义端点
        with patch("aidev_agent.api.ssm_client.settings") as mock_settings:
            mock_settings.BK_SSM_ENDPOINT = "https://custom-ssm.example.com"
            mock_settings.APP_CODE = "test_app"
            mock_settings.SECRET_KEY = "test_secret"
            client = SSMClient()
            assert client.base_url == "https://custom-ssm.example.com"

        # 2. 根据运行模式选择
        with patch("aidev_agent.api.ssm_client.settings") as mock_settings:
            mock_settings.BK_SSM_ENDPOINT = ""
            mock_settings.RUN_MODE = "PRODUCT"
            mock_settings.BK_SSM_SG_ENDPOINT = "https://sg-ssm.example.com"
            mock_settings.APP_CODE = "test_app"
            mock_settings.SECRET_KEY = "test_secret"
            client = SSMClient()
            assert client.base_url == "https://sg-ssm.example.com"

        with patch("aidev_agent.api.ssm_client.settings") as mock_settings:
            mock_settings.BK_SSM_ENDPOINT = ""
            mock_settings.RUN_MODE = "DEVELOPMENT"
            mock_settings.BK_SSM_BKOP_ENDPOINT = "https://bkop-ssm.example.com"
            mock_settings.APP_CODE = "test_app"
            mock_settings.SECRET_KEY = "test_secret"
            client = SSMClient()
            assert client.base_url == "https://bkop-ssm.example.com"


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


class TestSSMConvenienceFunctions:
    """SSM便捷函数测试"""

    def test_get_ssm_client_function(self):
        """测试get_ssm_client便捷函数"""
        # 测试默认参数
        client = get_ssm_client(
            base_url="https://convenience.example.com", app_code="convenience_app", app_secret="convenience_secret"
        )

        assert isinstance(client, SSMClient)
        assert client.base_url == "https://convenience.example.com"
        assert client.app_code == "convenience_app"
        assert client.app_secret == "convenience_secret"

    @responses.activate
    def test_error_handling(self):
        """测试错误处理"""
        # 清理可能存在的单例
        if hasattr(SSMClient, "_instance"):
            delattr(SSMClient, "_instance")

        # 先创建一个实例用于测试
        SSMClient.get_instance(
            base_url="https://error-test.example.com", app_code="error_app", app_secret="error_secret"
        )

        # 测试网络错误
        responses.add(
            responses.POST,
            "https://error-test.example.com/api/v1/auth/access-tokens",
            json={"error": "network error"},
            status=500,
        )

        client = SSMClient.get_instance()
        try:
            client.get_client_access_token()
            assert False, "应该抛出异常"
        except SSMException as e:
            assert "SSM请求失败" in str(e)

        # 测试API返回错误
        responses.reset()
        responses.add(
            responses.POST,
            "https://error-test.example.com/api/v1/auth/access-tokens",
            json={"code": 40001, "message": "应用凭据无效", "data": None},
            status=200,
        )

        try:
            client.get_client_access_token()
            assert False, "应该抛出异常"
        except SSMException as e:
            assert "应用凭据无效" in str(e)


class TestSSMRequestIntegration:
    """SSM Django request集成测试"""

    def setup_method(self):
        """测试前准备"""
        self.base_url = "https://test-integration.example.com"
        self.app_code = "integration_app"
        self.app_secret = "integration_secret"
        self.client = SSMClient(
            base_url=self.base_url,
            app_code=self.app_code,
            app_secret=self.app_secret,
        )

    def test_request_context_priority(self):
        """测试request上下文参数优先级"""
        # 创建mock request
        request_mock = Mock()
        request_mock.user.username = "request_user"
        request_mock.META = {"HTTP_AIDEV_TICKET": "request_token"}
        request_mock.COOKIES = {}

        # 测试手动参数覆盖request中的参数
        self.client.set_request_context(
            request=request_mock,
            username="manual_user",  # 这个应该覆盖request中的用户名
            bk_token="manual_token",  # 这个应该覆盖request中的token
        )

        assert self.client._request_context["username"] == "manual_user"
        assert self.client._request_context["bk_token"] == "manual_token"

    def test_request_information_extraction(self):
        """测试request信息提取功能"""
        # 测试bk_token提取：META优先级高于COOKIES
        request_mock = Mock()
        request_mock.META = {"HTTP_AIDEV_TICKET": "meta_token"}
        request_mock.COOKIES = {"bk_token": "cookie_token"}
        token = self.client._extract_bk_token_from_request(request_mock)
        assert token == "meta_token"  # META优先

        # 测试COOKIES作为fallback
        request_mock.META = {}
        token = self.client._extract_bk_token_from_request(request_mock)
        assert token == "cookie_token"

        # 测试多种header格式支持
        request_mock.META = {"HTTP_BK_TOKEN": "bk_token_header"}
        request_mock.COOKIES = {}
        token = self.client._extract_bk_token_from_request(request_mock)
        assert token == "bk_token_header"

        # 测试HTTP_AIDEV_TICKET优先级更高
        request_mock.META = {"HTTP_AIDEV_TICKET": "aidev_ticket", "HTTP_BK_TOKEN": "bk_token_header"}
        token = self.client._extract_bk_token_from_request(request_mock)
        assert token == "aidev_ticket"

        # 测试用户名提取：request.user优先
        request_mock = Mock()
        request_mock.user.username = "django_user"
        request_mock.COOKIES = {"bk_uid": "cookie_user"}
        username = self.client._extract_username_from_request(request_mock)
        assert username == "django_user"

        # 测试从cookies提取（当request.user不可用时）
        request_mock = Mock()
        request_mock.user = None
        request_mock.COOKIES = {"bk_uid": "cookie_user"}
        username = self.client._extract_username_from_request(request_mock)
        assert username == "cookie_user"
