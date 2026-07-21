# -*- coding: utf-8 -*-

from django.urls import include, re_path
from rest_framework.routers import DefaultRouter

from .views.agent import AgentInfoViewSet
from .views.chat import ChatCompletionViewSet
from .views.chat_group import ChatGroupViewSet
from .views.flow_agent import FlowAgentViewSet
from .views.llm import LLMViewSet
from .views.session import (
    ChatSessionContentFeedbackViewSet,
    ChatSessionContentViewSet,
    ChatSessionShareView,
    ChatSessionViewSet,
)
from .views.user_operation import UserOperationViewSet

_router = DefaultRouter()
_router.register("agent", AgentInfoViewSet, "agent_info")
_router.register("chat_completion", ChatCompletionViewSet, "chat_completion")
_router.register("flow_agent", FlowAgentViewSet, "flow_agent")
_router.register("session", ChatSessionViewSet, "chat_session")
_router.register("session_content", ChatSessionContentViewSet, "chat_session_content")
_router.register("session_feedback", ChatSessionContentFeedbackViewSet, "chat_session_feedback")
_router.register("chat_group", ChatGroupViewSet, "chat_group")
_router.register("share", ChatSessionShareView, "share")
_router.register("user_operation", UserOperationViewSet, "user_operation")
_router.register("llm", LLMViewSet, "llm")


urlpatterns = [
    re_path("", include(_router.urls)),
]
