# -*- coding: utf-8 -*-
from importlib import import_module

__all__ = [
    "BkpluginAgentRunner",
    "build_bkplugin_runner",
    "build_bkplugin_runner_from_plugin",
    "normalize_execute_kwargs",
    "poll_bkplugin_agent",
    "record_plugin_poll_failure",
    "resolve_executor_username",
    "SessionManager",
]

_AGENT_BKPLUGIN_EXPORTS = frozenset(__all__) - {"SessionManager"}


def __getattr__(name: str):
    """按需加载服务导出，避免导入子模块时提前初始化 Django 模型。"""
    if name in _AGENT_BKPLUGIN_EXPORTS:
        module = import_module(".agent_bkplugin", __name__)
    elif name == "SessionManager":
        module = import_module(".agent_session", __name__)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = getattr(module, name)
    globals()[name] = value
    return value
