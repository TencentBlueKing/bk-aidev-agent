# -*- coding: utf-8 -*-

"""被调方 private 入口：供其它智能体（主调方）通过 apigw 调用本智能体。
1. 由 bk_plugin_framework 自动挂载（同 openapi/apis），各定义模块都从此处导入
2. 前辍：/bk_plugin/private/
3. 主调方调用权限由 aidev_bkplugin.private 内的权限类调用平台接口校验
"""

from django.urls import include, path

urlpatterns = (path("", include("aidev_bkplugin.private.urls")),)
