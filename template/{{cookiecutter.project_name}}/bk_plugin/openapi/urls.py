# -*- coding: utf-8 -*-

"""
此文件为蓝鲸插件默认加载的url文件，使用应用态接口鉴权，其它各定义模块都从此处导入
1. 位置：bk_plugin_framework/services/bpf_service/urls.py
2. 前辍：/openapi/
"""

from django.urls import include, path

urlpatterns = (path("agent/", include("aidev_bkplugin.urls")),)
