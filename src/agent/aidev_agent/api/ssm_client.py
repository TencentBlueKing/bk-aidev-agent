# -*- coding: utf-8 -*-
"""SSM客户端：支持外部版本的access_token获取、刷新和校验功能"""

import threading
import time
from dataclasses import dataclass
from logging import getLogger
from typing import Any, Dict, Optional

import requests

from aidev_agent.config import settings
from aidev_agent.exceptions import AIDevException

logger = getLogger(__name__)


class SSMException(AIDevException):
    """SSM客户端异常"""

    MESSAGE = "SSM客户端异常"


@dataclass
class TokenInfo:
    """Token信息"""

    access_token: str
    refresh_token: str
    expires_in: int
    created_at: float
    identity: Dict

    @property
    def is_expired(self) -> bool:
        """检查token是否过期（提前5分钟认为过期）"""
        return time.time() > (self.created_at + self.expires_in - 300)

    @property
    def remaining_time(self) -> int:
        """剩余有效时间（秒）"""
        return max(0, int(self.created_at + self.expires_in - time.time()))


class SSMClient:
    """SSM客户端，提供access_token的获取、刷新、校验功能"""

    def __init__(
        self,
        base_url: str = None,
        app_code: str = None,
        app_secret: str = None,
        timeout: int = 15,
    ):
        self.base_url = (base_url or self._get_default_endpoint()).rstrip("/")
        self.app_code = app_code or settings.APP_CODE
        self.app_secret = app_secret or settings.SECRET_KEY
        self.timeout = timeout

        # Token缓存 {cache_key: TokenInfo}
        self._token_cache: Dict[str, TokenInfo] = {}
        self._cache_lock = threading.RLock()

        # Request上下文，用于存储从request中提取的用户信息
        self._request_context: Dict = {}

        if not self.app_code or not self.app_secret:
            raise SSMException("app_code 和 app_secret 必须提供")

        if not self.base_url:
            raise SSMException("SSM endpoint 未配置")

    def _get_default_endpoint(self) -> str:
        """获取默认的SSM端点"""
        if settings.BK_SSM_ENDPOINT:
            return settings.BK_SSM_ENDPOINT

        # 根据运行环境自动选择
        if hasattr(settings, "RUN_MODE"):
            if settings.RUN_MODE == "PRODUCT":
                return settings.BK_SSM_SG_ENDPOINT
            else:
                return settings.BK_SSM_BKOP_ENDPOINT

        # 默认使用BKOP环境
        return settings.BK_SSM_BKOP_ENDPOINT

    def _headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "X-Bk-App-Code": self.app_code,
            "X-Bk-App-Secret": self.app_secret,
            "Content-Type": "application/json",
        }

    def _make_request(self, method: str, path: str, data: Dict = None) -> Dict:
        """发起HTTP请求"""
        url = f"{self.base_url}{path}"
        headers = self._headers()

        try:
            if method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data or {}, timeout=self.timeout)
            else:
                response = requests.get(url, headers=headers, params=data or {}, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"SSM请求失败: {url}, error: {e}")
            raise SSMException(f"SSM请求失败: {str(e)}")

    def _get_cache_key(self, username: str = None) -> str:
        """生成缓存key"""
        if username:
            return f"{self.app_code}:{username}:user"
        else:
            return f"{self.app_code}:client"

    def _extract_bk_token_from_request(self, request) -> Optional[str]:
        """从Django request中提取bk_token"""
        if not request:
            return None

        # 尝试从不同位置获取bk_token
        # 1. 从META中获取（通过header传递）
        if hasattr(request, "META"):
            bk_token = request.META.get("HTTP_AIDEV_TICKET") or request.META.get("HTTP_BK_TOKEN")
            if bk_token:
                return bk_token

        # 2. 从COOKIES中获取
        if hasattr(request, "COOKIES"):
            bk_token = request.COOKIES.get("bk_token") or request.COOKIES.get("bk_ticket")
            if bk_token:
                return bk_token

        return None

    def _extract_username_from_request(self, request) -> Optional[str]:
        """从Django request中提取用户名"""
        if not request:
            return None

        # 从request.user获取用户名
        if hasattr(request, "user") and hasattr(request.user, "username"):
            return request.user.username

        # 从COOKIES中获取
        if hasattr(request, "COOKIES"):
            username = request.COOKIES.get("bk_uid")
            if username:
                return username

        return None

    def set_request_context(self, request=None, username: str = None, bk_token: str = None):
        """设置request上下文信息

        Args:
            request: Django request对象
            username: 用户名（可选，会覆盖从request中提取的用户名）
            bk_token: BK Token（可选，会覆盖从request中提取的token）
        """
        if request:
            extracted_username = self._extract_username_from_request(request)
            extracted_bk_token = self._extract_bk_token_from_request(request)

            self._request_context = {
                "is_user_mode": bool(extracted_username and extracted_bk_token),
                "username": username or extracted_username,
                "bk_token": bk_token or extracted_bk_token,
                "request": request,
            }
        else:
            self._request_context = {
                "is_user_mode": bool(username and bk_token),
                "username": username,
                "bk_token": bk_token,
                "request": None,
            }

        logger.debug(
            f"设置request上下文: user_mode={self._request_context['is_user_mode']}, username={self._request_context.get('username')}"
        )

    def get_user_access_token(self, username: str = None, bk_token: str = None, request=None) -> str:
        """
        获取用户态access_token

        Args:
            username: 用户名（如果为空则从request上下文或request参数获取）
            bk_token: 用户登录token（如果为空则从request上下文或request参数获取）
            request: Django request对象（可选，会从中提取用户信息）

        Returns:
            str: 有效的access_token
        """
        # 如果提供了request参数，临时设置上下文
        if request:
            self.set_request_context(request, username, bk_token)
            username = username or self._request_context.get("username")
            bk_token = bk_token or self._request_context.get("bk_token")
        # 如果没有提供参数，尝试从request上下文获取
        if not username or not bk_token:
            if self._request_context.get("is_user_mode"):
                username = username or self._request_context.get("username")
                bk_token = bk_token or self._request_context.get("bk_token")

            if not username or not bk_token:
                raise SSMException("未提供用户名或bk_token，且request上下文中也未找到相关信息")
        cache_key = self._get_cache_key(username)

        with self._cache_lock:
            # 检查缓存
            cached_token = self._token_cache.get(cache_key)
            if cached_token and not cached_token.is_expired:
                logger.debug(f"使用缓存的用户态token: {username}")
                return cached_token.access_token

            # 如果有缓存但过期了，尝试刷新
            if cached_token and cached_token.is_expired:
                try:
                    logger.info(f"用户态token过期，尝试刷新: {username}")
                    refresh_response = self._refresh_access_token(cached_token.refresh_token)

                    if refresh_response.get("code") == 0:
                        response_data = refresh_response["data"]
                        refreshed_token = TokenInfo(
                            access_token=response_data["access_token"],
                            refresh_token=response_data["refresh_token"],
                            expires_in=response_data["expires_in"],
                            created_at=time.time(),
                            identity=response_data["identity"],
                        )
                        self._token_cache[cache_key] = refreshed_token
                        logger.info(f"成功刷新用户态token: {username}")
                        return refreshed_token.access_token
                except Exception as e:
                    logger.warning(f"刷新用户态token失败，将重新创建: {e}")

            # 创建新的用户态token
            logger.info(f"创建新的用户态token: {username}")
            response = self._create_access_token(
                grant_type="authorization_code", id_provider="bk_login", bk_token=bk_token
            )

            if response.get("code") != 0:
                raise SSMException(f"创建用户态access_token失败: {response.get('message', '未知错误')}")

            # 缓存新token
            response_data = response["data"]
            token_info = TokenInfo(
                access_token=response_data["access_token"],
                refresh_token=response_data["refresh_token"],
                expires_in=response_data["expires_in"],
                created_at=time.time(),
                identity=response_data["identity"],
            )
            self._token_cache[cache_key] = token_info
            logger.info(f"成功创建并缓存用户态token: {username}")

            return token_info.access_token

    def get_client_access_token(self) -> str:
        """
        获取应用态access_token

        Returns:
            str: 有效的access_token
        """
        cache_key = self._get_cache_key()

        with self._cache_lock:
            # 检查缓存
            cached_token = self._token_cache.get(cache_key)
            if cached_token and not cached_token.is_expired:
                logger.debug("使用缓存的应用态token")
                return cached_token.access_token

            # 如果有缓存但过期了，尝试刷新
            if cached_token and cached_token.is_expired:
                try:
                    logger.info("应用态token过期，尝试刷新")
                    refresh_response = self._refresh_access_token(cached_token.refresh_token)

                    if refresh_response.get("code") == 0:
                        response_data = refresh_response["data"]
                        refreshed_token = TokenInfo(
                            access_token=response_data["access_token"],
                            refresh_token=response_data["refresh_token"],
                            expires_in=response_data["expires_in"],
                            created_at=time.time(),
                            identity=response_data["identity"],
                        )
                        self._token_cache[cache_key] = refreshed_token
                        logger.info("成功刷新应用态token")
                        return refreshed_token.access_token
                except Exception as e:
                    logger.warning(f"刷新应用态token失败，将重新创建: {e}")

            # 创建新的应用态token
            logger.info("创建新的应用态token")
            response = self._create_access_token(grant_type="client_credentials", id_provider="client")

            if response.get("code") != 0:
                raise SSMException(f"创建应用态access_token失败: {response.get('message', '未知错误')}")

            # 缓存新token
            response_data = response["data"]
            token_info = TokenInfo(
                access_token=response_data["access_token"],
                refresh_token=response_data["refresh_token"],
                expires_in=response_data["expires_in"],
                created_at=time.time(),
                identity=response_data["identity"],
            )
            self._token_cache[cache_key] = token_info
            logger.info("成功创建并缓存应用态token")

            return token_info.access_token

    def _create_access_token(self, grant_type: str, id_provider: str, bk_token: Optional[str] = None) -> Dict[str, Any]:
        """创建access_token"""
        payload = {
            "grant_type": grant_type,
            "id_provider": id_provider,
        }
        if bk_token:
            payload["bk_token"] = bk_token

        return self._make_request("POST", "/api/v1/auth/access-tokens", payload)

    def _refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """刷新access_token"""
        payload = {"refresh_token": refresh_token}
        return self._make_request("POST", "/api/v1/auth/access-tokens/refresh", payload)

    def clear_cache(self, username: str = None):
        """清理token缓存"""
        with self._cache_lock:
            if username is not None:
                cache_key = self._get_cache_key(username)
                self._token_cache.pop(cache_key, None)
                logger.info(f"清理用户态缓存: {username}")
            else:
                self._token_cache.clear()
                logger.info("清理所有token缓存")

    def verify_access_token(self, access_token: str) -> Dict[str, Any]:
        """校验access_token"""
        payload = {"access_token": access_token}
        return self._make_request("POST", "/api/v1/auth/access-tokens/verify", payload)

    def get_cache_info(self) -> Dict[str, Dict]:
        """获取缓存信息（用于调试）"""
        with self._cache_lock:
            info = {}
            for key, token in self._token_cache.items():
                info[key] = {
                    "is_expired": token.is_expired,
                    "remaining_time": token.remaining_time,
                    "identity": token.identity,
                }
            return info

    @classmethod
    def get_instance(cls, base_url: str = None, app_code: str = None, app_secret: str = None) -> "SSMClient":
        """获取SSM客户端实例（单例模式）

        Args:
            base_url: SSM服务地址（可选）
            app_code: 应用代码（可选）
            app_secret: 应用密钥（可选）

        Returns:
            SSMClient: SSM客户端实例
        """
        if not hasattr(cls, "_instance"):
            cls._instance = cls(base_url=base_url, app_code=app_code, app_secret=app_secret)
        return cls._instance

    def get_access_token_for_request(self, request) -> str:
        """为主站代码提供的便捷方法：从request获取用户态access_token

        这个方法专门为主站代码集成设计，会自动从Django request中提取用户信息

        Args:
            request: Django request对象

        Returns:
            str: 有效的access_token

        Raises:
            SSMException: 当无法从request中提取用户信息时
        """
        if not request:
            raise SSMException("request参数不能为空")

        return self.get_user_access_token(request=request)


# 模块级便捷函数
def get_ssm_client(base_url: str = None, app_code: str = None, app_secret: str = None) -> SSMClient:
    """获取SSM客户端实例的便捷函数

    Args:
        base_url: SSM服务地址（可选，会使用配置中的默认值）
        app_code: 应用代码（可选，会使用配置中的默认值）
        app_secret: 应用密钥（可选，会使用配置中的默认值）

    Returns:
        SSMClient: SSM客户端实例
    """
    return SSMClient(base_url=base_url, app_code=app_code, app_secret=app_secret)


def get_user_access_token_from_request(request) -> str:
    """从Django request获取用户态access_token的便捷函数

    这是一个全局便捷函数，适用于快速集成到现有代码中

    Args:
        request: Django request对象

    Returns:
        str: 有效的access_token

    Raises:
        SSMException: 当无法获取token时
    """
    client = SSMClient.get_instance()
    return client.get_access_token_for_request(request)
