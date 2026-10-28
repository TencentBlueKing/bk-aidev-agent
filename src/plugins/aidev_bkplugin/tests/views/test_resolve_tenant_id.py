# -*- coding: utf-8 -*-
"""``resolve_tenant_id`` 多级优先级单测：user → app → jwt.payload[user/app] → ""。

为避免引入整个 Django / bk_plugin_framework 运行时栈，import 目标模块前先把
``views/base.py`` 的外部重依赖以 stub 注入 ``sys.modules``（被测函数不依赖它们）。
"""

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _stub(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


@pytest.fixture(scope="module")
def resolve_tenant_id():
    """按需 stub 外部重依赖后，import 真实的 resolve_tenant_id。

    ``sys.modules`` 改动经 ``MonkeyPatch`` 完成，结束后自动还原，避免污染其他测试模块。
    """
    with pytest.MonkeyPatch.context() as mp:
        stubs = {
            # bk_plugin_framework.kit.decorators.inject_user_token
            "bk_plugin_framework": {},
            "bk_plugin_framework.kit": {},
            "bk_plugin_framework.kit.decorators": {"inject_user_token": lambda f: f},
            # aidev_bkplugin 内部重依赖（resolve_tenant_id 不使用，仅为满足 base.py import）
            "aidev_bkplugin.packages": {},
            "aidev_bkplugin.packages.drf": {},
            "aidev_bkplugin.packages.drf.authentication": {"custom_authentication_classes": []},
            "aidev_bkplugin.packages.drf.decorators": {"login_exempt": lambda f: f},
            "aidev_bkplugin.packages.drf.renderers": {"get_response_trace_id": lambda r: ""},
            "aidev_bkplugin.permissions": {"AgentPluginPermission": object},
            "aidev_bkplugin.services": {},
            "aidev_bkplugin.services.agent_builder": {"LLMOverrideResourceManager": MagicMock()},
            "aidev_bkplugin.services.agent_helpers": {"AgentHelper": MagicMock()},
        }
        for name, attrs in stubs.items():
            mp.setitem(sys.modules, name, _stub(name, **attrs))

        # 同目录下 test_session_pv_files_views.py 在模块级把整个 ``views.base`` 替换成 stub
        # （其 resolve_tenant_id 恒返回 ""）。pytest 先 collect（执行该模块级代码）再 run，
        # 故此处必须先剔除被污染的缓存再 import，否则拿到的是 stub 而非真实实现。
        mp.delitem(sys.modules, "aidev_bkplugin.views.base", raising=False)

        from aidev_bkplugin.views.base import resolve_tenant_id as fn

        yield fn


class TestPriority:
    def test_user_tenant_wins(self, resolve_tenant_id):
        """user.tenant_id 优先于 app.tenant_id 与 jwt。"""
        request = SimpleNamespace(
            user=SimpleNamespace(tenant_id="from-user"),
            app=SimpleNamespace(tenant_id="from-app"),
            jwt=SimpleNamespace(payload={"user": {"tenant_id": "from-jwt-user"}}),
        )
        assert resolve_tenant_id(request) == "from-user"

    def test_app_tenant_when_user_empty(self, resolve_tenant_id):
        """user 为空时回落 app.tenant_id（系统租户智能体应用态场景）。"""
        request = SimpleNamespace(
            user=SimpleNamespace(tenant_id=""),
            app=SimpleNamespace(tenant_id="from-app"),
            jwt=SimpleNamespace(payload={"app": {"tenant_id": "from-jwt-app"}}),
        )
        assert resolve_tenant_id(request) == "from-app"

    def test_jwt_user_when_user_and_app_empty(self, resolve_tenant_id):
        """user/app 都取不到时，回落 jwt.payload['user'].tenant_id。"""
        request = SimpleNamespace(
            user=SimpleNamespace(tenant_id=""),
            app=SimpleNamespace(tenant_id=""),
            jwt=SimpleNamespace(payload={"user": {"tenant_id": "from-jwt-user"}}),
        )
        assert resolve_tenant_id(request) == "from-jwt-user"

    def test_jwt_app_when_jwt_user_missing(self, resolve_tenant_id):
        """jwt.payload 无 user.tenant_id 时取 app.tenant_id。"""
        request = SimpleNamespace(
            user=None,
            app=None,
            jwt=SimpleNamespace(payload={"user": {}, "app": {"tenant_id": "from-jwt-app"}}),
        )
        assert resolve_tenant_id(request) == "from-jwt-app"


class TestEmptyFallback:
    def test_all_empty_returns_empty(self, resolve_tenant_id):
        """全部取不到 → 空串（单租户现状，不带头）。"""
        request = SimpleNamespace(
            user=SimpleNamespace(tenant_id=""),
            app=SimpleNamespace(tenant_id=""),
            jwt=SimpleNamespace(payload={}),
        )
        assert resolve_tenant_id(request) == ""

    def test_no_attrs_returns_empty(self, resolve_tenant_id):
        """request 无 user/app/jwt 属性 → 空串，getattr 防御不抛异常。"""
        request = SimpleNamespace()
        assert resolve_tenant_id(request) == ""

    def test_missing_user_tenant_attr(self, resolve_tenant_id):
        """user 存在但无 tenant_id 属性 → 不报错，继续回落。"""
        request = SimpleNamespace(user=object(), app=SimpleNamespace(tenant_id="from-app"))
        assert resolve_tenant_id(request) == "from-app"

    def test_non_dict_payload_safe(self, resolve_tenant_id):
        """jwt.payload 非 dict → 安全退化为空串。"""
        request = SimpleNamespace(user=None, app=None, jwt=SimpleNamespace(payload="not-a-dict"))
        assert resolve_tenant_id(request) == ""
