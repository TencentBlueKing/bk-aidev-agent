from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from agent.services.agent import get_agent_config_info


class AgentPluginPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        # 检查用户是否有agent的access_agent权限
        agent_info = get_agent_config_info(request.user.username)
        if not agent_info.get("allowed_access", False):
            raise PermissionDenied(
                detail=f"用户{request.user.username}没有使用此插件的权限", code="NO_ACCESS_AGENT_PERMISSION"
            )

        return True
