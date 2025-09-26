from typing import ClassVar

from django.core.cache import cache
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from .services.agent import get_agent_config_info


class AgentPluginPermission(permissions.BasePermission):
    CACHE_KEY_PREFIX: ClassVar[str] = "user_permission"
    CACHE_ALLOWED_TIMEOUT: ClassVar[int] = 60 * 60
    CACHE_NOT_ALLOWED_TIMEOUT: ClassVar[int] = 60

    def has_permission(self, request, view):
        # 检查用户是否有agent的access_agent权限
        allowed_access = self._get_allowed_access(request.user.username)
        if not allowed_access:
            raise PermissionDenied(
                detail=f"用户{request.user.username}没有使用此插件的权限", code="NO_ACCESS_AGENT_PERMISSION"
            )

        return True

    def _get_allowed_access(self, username) -> bool:
        cache_key = f"{self.CACHE_KEY_PREFIX}_{username}"
        allowed_access = cache.get(cache_key)

        if allowed_access is None:
            agent_info = get_agent_config_info(username)
            allowed_access = agent_info.get("allowed_access", False)
            if allowed_access:
                cache.set(cache_key, allowed_access, timeout=self.CACHE_ALLOWED_TIMEOUT)
            else:
                cache.set(cache_key, allowed_access, timeout=self.CACHE_NOT_ALLOWED_TIMEOUT)
        return allowed_access
