# -*- coding: utf-8 -*-

from django.urls import include, re_path
from rest_framework.routers import DefaultRouter

from .views.builtin import (
    AgentInfoViewSet,
    ChatCompletionViewSet,
    ChatGroupViewSet,
    ChatSessionContentFeedbackViewSet,
    ChatSessionContentViewSet,
    ChatSessionViewSet, ChatSessionShareView,
)

_router = DefaultRouter()
_router.register("agent", AgentInfoViewSet, "agent_info")
_router.register("chat_completion", ChatCompletionViewSet, "chat_completion")
_router.register("session", ChatSessionViewSet, "chat_session")
_router.register("session_content", ChatSessionContentViewSet, "chat_session_content")
_router.register("session_feedback", ChatSessionContentFeedbackViewSet, "chat_session_feedback")
_router.register("chat_group", ChatGroupViewSet, "chat_group")
_router.register("share", ChatSessionShareView, "share")


urlpatterns = [
    re_path("", include(_router.urls)),
]
