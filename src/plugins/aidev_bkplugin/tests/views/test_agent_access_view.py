# -*- coding: utf-8 -*-
"""应用态接口：访问者授权状态与权限申请单测。"""

from types import SimpleNamespace
from unittest.mock import patch

from aidev_bkplugin.openapi.views import OpenapiAgentAccessViewSet
from aidev_bkplugin.packages.apigw.permissions import ApigwPermission


def _request(username="alice"):
    return SimpleNamespace(user=SimpleNamespace(username=username))


def test_skips_agent_use_permission():
    assert OpenapiAgentAccessViewSet.permission_classes == [ApigwPermission]


def test_list_returns_platform_status():
    status = {"status": "authorization_pending", "apply_url": "https://iam.example.com/apply"}
    with patch("aidev_bkplugin.openapi.views.resource_manager") as mock_rm:
        mock_rm.return_value.get_agent_access_status.return_value = status

        response = OpenapiAgentAccessViewSet().list(_request())

    assert response.data == status
    mock_rm.return_value.get_agent_access_status.assert_called_once_with(username="alice")


def test_apply_returns_platform_apply_url():
    with patch("aidev_bkplugin.openapi.views.resource_manager") as mock_rm:
        mock_rm.return_value.apply_agent_access.return_value = {"apply_url": "https://iam.example.com/apply"}

        response = OpenapiAgentAccessViewSet().apply(_request())

    assert response.data == {"apply_url": "https://iam.example.com/apply"}
    mock_rm.return_value.apply_agent_access.assert_called_once_with(username="alice")
