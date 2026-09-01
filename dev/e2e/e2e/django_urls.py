"""URL overlay that keeps local E2E authentication out of template code."""

from aidev_ai_blueking.views import IndexView
from bk_plugin.patch.urls import urlpatterns as base_urlpatterns
from blueapps.account.decorators import login_exempt
from django.urls import re_path

urlpatterns = [
    re_path(r"^chat-window/?$", login_exempt(IndexView.as_view()), name="chat-window"),
    *(pattern for pattern in base_urlpatterns if getattr(pattern, "name", None) != "chat-window"),
]
