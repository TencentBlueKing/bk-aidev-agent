# -*- coding: utf-8 -*-

"""
智能体应用态接口
"""

from django.urls import include, re_path
from rest_framework.routers import DefaultRouter

from agent.views.builtin import (
    ChatCompletionViewSet,
)

_router = DefaultRouter()
_router.register("chat_completion", ChatCompletionViewSet, "chat_completion")


urlpatterns = [
    re_path("", include(_router.urls)),
]
