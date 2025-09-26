"""
URL routing for aidev_wxbot using DRF ViewSets.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from aidev_wxbot.wxaibot.views import WxAiBotViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r"", WxAiBotViewSet, basename="wxaibot")

urlpatterns = [
    # DRF ViewSet路由
    path("", include(router.urls)),
]
