# -*- coding: utf-8 -*-

from django.urls import include, re_path
from rest_framework.routers import DefaultRouter

from agent.views.builtin import (
    AgentInfoViewSet,
    ChatCompletionViewSet,
    ChatGroupViewSet,
    ChatSessionContentViewSet,
    ChatSessionViewSet,
)

_router = DefaultRouter()
_router.register("agent", AgentInfoViewSet, "agent_info")
_router.register("chat_completion", ChatCompletionViewSet, "chat_completion")
_router.register("session", ChatSessionViewSet, "chat_session")
_router.register("session_content", ChatSessionContentViewSet, "chat_session_content")
_router.register("chat_group", ChatGroupViewSet, "chat_group")


urlpatterns = [
    re_path("", include(_router.urls)),
]
