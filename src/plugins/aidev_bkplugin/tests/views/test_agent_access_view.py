# -*- coding: utf-8 -*-
"""应用态接口：访问者授权状态与权限申请单测。"""

from aidev_bkplugin.openapi.views import OpenapiAgentAccessViewSet
from aidev_bkplugin.packages.apigw.permissions import ApigwPermission


def test_skips_agent_use_permission():
    """未授权访问者也要能查状态和申请，不能挂智能体使用权限校验。"""
    assert OpenapiAgentAccessViewSet.permission_classes == [ApigwPermission]
