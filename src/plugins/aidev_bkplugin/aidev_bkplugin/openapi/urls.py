# -*- coding: utf-8 -*-

"""
应用态接口
1. 上层入口：bk_plugin/openapi/urls.py
2. 用户信息由接入系统通过 Header 头传入，Key 是 X-BKAIDEV-USER
"""

from django.urls import include, re_path
from rest_framework.routers import DefaultRouter

from aidev_bkplugin.openapi.views import OpenapiChatCompletionViewSet

_router = DefaultRouter()
_router.register("chat_completion", OpenapiChatCompletionViewSet, "chat_completion")


urlpatterns = [
    re_path("agent/", include(_router.urls)),
]
