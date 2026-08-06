# -*- coding: utf-8 -*-
"""Test-only stubs for dependencies provided by the BK plugin runtime."""

import sys
from types import ModuleType
from unittest.mock import MagicMock


def inject_user_token(func):
    return func


framework_module = ModuleType("bk_plugin_framework")
kit_module = ModuleType("bk_plugin_framework.kit")
decorators_module = ModuleType("bk_plugin_framework.kit.decorators")
decorators_module.inject_user_token = inject_user_token
kit_module.decorators = decorators_module
framework_module.kit = kit_module

models_module = ModuleType("aidev_bkplugin.models")
models_module.Checkpoint = MagicMock()
models_module.Write = MagicMock()

sys.modules.setdefault("bk_plugin_framework", framework_module)
sys.modules.setdefault("bk_plugin_framework.kit", kit_module)
sys.modules.setdefault("bk_plugin_framework.kit.decorators", decorators_module)
sys.modules.setdefault("aidev_bkplugin.models", models_module)
