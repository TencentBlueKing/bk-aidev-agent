# -*- coding: utf-8 -*-

from django.urls import re_path

from .views import IndexView

urlpatterns = [
    re_path(r"^$", IndexView.as_view(), name="index"),
    re_path(r"^page/$", IndexView.as_view(), name="index"),
    re_path(r"^side-slider/$", IndexView.as_view(), name="index"),
    re_path(r"^403/$", IndexView.as_view(), name="index"),
    re_path(r"^share-page/.*$", IndexView.as_view(), name="index"),
]
