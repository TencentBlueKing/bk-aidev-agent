# -*- coding: utf-8 -*-
"""文件路径遍历防护测试（glob/grep）。

覆盖 ``validate_path`` 的遍历防护（``..`` 拒绝，默认生效，无需任何配置）。
"""

from __future__ import annotations

from tempfile import TemporaryDirectory

import pytest
from aidev_agent.core.tools.runtime_tools.local_backend import FilesystemBackend
from aidev_agent.core.tools.runtime_tools.provider import (
    RuntimeBackendResolver,
    get_glob_tool,
    get_grep_tool,
)
from aidev_agent.packages.security.command.command_security import validate_path


def _local_provider(backend: FilesystemBackend, security_settings=None) -> RuntimeBackendResolver:
    return RuntimeBackendResolver(default_runtime="local", security_settings=security_settings).register_runtime(
        "local", backend
    )


class TestValidatePathReservedPrefixGuard:
    """``validate_path`` 的 ``allowed_prefixes`` 形参（当前无生产消费方，保留备用）。"""

    def test_resolver_security_settings_defaults_to_none(self):
        """resolver 未注入 security_settings 时 property 为 None。"""
        assert RuntimeBackendResolver(default_runtime="local").security_settings is None

    def test_validate_path_allows_storage_prefix(self):
        """$STORAGE_PATH 前缀按原文放行（PaaS 沙箱路径）。"""
        result = validate_path("$STORAGE_PATH/session/x", allowed_prefixes=["$STORAGE_PATH"])
        assert result == "$STORAGE_PATH/session/x"


class TestGlobGrepTraversalGuard:
    """glob/grep 工具的路径遍历防护。"""

    def test_glob_rejects_traversal(self):
        """glob 的搜索目录不允许路径遍历（默认生效，无需配置白名单）。"""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_glob_tool(provider)

            with pytest.raises(ValueError, match="Path traversal not allowed"):
                tool.invoke({"pattern": "*.txt", "path": "../etc", "target_runtime": "local"})

    def test_grep_rejects_traversal(self):
        """grep 的搜索目录不允许路径遍历（默认生效，无需配置白名单）。"""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_grep_tool(provider)

            with pytest.raises(ValueError, match="Path traversal not allowed"):
                tool.invoke({"pattern": "root", "path": "../etc", "target_runtime": "local"})
