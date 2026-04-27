# -*- coding: utf-8 -*-
"""Tests for RuntimeBackendResolver.

This module contains tests for filesystem tools and runtime routing.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from aidev_agent.core.tools.runtime_tools.local_backend import FilesystemBackend
from aidev_agent.core.tools.runtime_tools.provider import (
    DEFAULT_READ_LIMIT,
    DEFAULT_READ_OFFSET,
    RuntimeBackendResolver,
    _validate_path,
    get_client_tools_with_runtime,
    get_edit_file_tool,
    get_execute_tool,
    get_glob_tool,
    get_grep_tool,
    get_ls_tool,
    get_read_file_tool,
    get_write_file_tool,
)
from aidev_agent.core.tools.runtime_tools.types import ExecuteResult


def _local_provider(backend: FilesystemBackend) -> RuntimeBackendResolver:
    return RuntimeBackendResolver(default_runtime="local").register_runtime("local", backend)


def _schema_properties(tool) -> dict:
    # pydantic v1: schema(); pydantic v2: model_json_schema()
    if getattr(tool, "args_schema", None) is None:
        return {}

    schema = None
    if hasattr(tool.args_schema, "schema"):
        schema = tool.args_schema.schema()  # type: ignore[attr-defined]
    elif hasattr(tool.args_schema, "model_json_schema"):
        schema = tool.args_schema.model_json_schema()  # type: ignore[attr-defined]

    if not isinstance(schema, dict):
        return {}
    return schema.get("properties", {}) or {}


class TestValidatePath:
    """Test _validate_path function."""

    def test_validate_path_simple(self):
        """Test validating simple path."""
        result = _validate_path("foo/bar")
        assert result == "/foo/bar"

    def test_validate_path_with_leading_slash(self):
        """Test validating path with leading slash."""
        result = _validate_path("/foo/bar")
        assert result == "/foo/bar"

    def test_validate_path_normalizes(self):
        """Test that path is normalized."""
        result = _validate_path("/./foo//bar")
        assert result == "/foo/bar"

    def test_validate_path_prevents_traversal(self):
        """Test that path traversal is prevented."""
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            _validate_path("../etc/passwd")

        with pytest.raises(ValueError, match="Path traversal not allowed"):
            _validate_path("foo/../../etc/passwd")

    def test_validate_path_prevents_home(self):
        """Test that home directory access is prevented."""
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            _validate_path("~/.bashrc")

    def test_validate_path_windows_absolute(self):
        """Test that Windows absolute paths are rejected."""
        with pytest.raises(ValueError, match="Windows absolute paths are not supported"):
            _validate_path("C:/Users/file.txt")

        with pytest.raises(ValueError, match="Windows absolute paths are not supported"):
            _validate_path("D:\\Users\\file.txt")

    def test_validate_path_with_allowed_prefixes(self):
        """Test validating path with allowed prefixes."""
        result = _validate_path("/data/file.txt", allowed_prefixes=["/data/", "/workspace/"])
        assert result == "/data/file.txt"

    def test_validate_path_not_in_allowed_prefixes(self):
        """Test that paths outside allowed prefixes are rejected."""
        with pytest.raises(ValueError, match="must start with one of"):
            _validate_path("/etc/file.txt", allowed_prefixes=["/data/", "/workspace/"])


class TestRuntimeBackendResolver:
    def test_single_runtime_hides_runtime_param(self):
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tools = get_client_tools_with_runtime(provider)

            ls_tool = next(t for t in tools if t.name == "ls")
            props = _schema_properties(ls_tool)
            assert "target_runtime" in props

    def test_multi_runtime_includes_runtime_param(self):
        with TemporaryDirectory() as d1, TemporaryDirectory() as d2:
            provider = RuntimeBackendResolver(default_runtime="local")
            provider.register_runtime("local", FilesystemBackend(root_dir=d1))
            provider.register_runtime("sandbox_1", FilesystemBackend(root_dir=d2))

            tools = get_client_tools_with_runtime(provider)
            execute_tool = next(t for t in tools if t.name == "execute")
            props = _schema_properties(execute_tool)
            assert "target_runtime" in props

            runtime_desc = props["target_runtime"].get("description", "")
            assert "local" in runtime_desc
            assert "sandbox_1" in runtime_desc

    def test_runtime_routing(self):
        class FakeBackend:
            def __init__(self, label: str):
                self.label = label

            def execute(self, command: str) -> ExecuteResult:
                return ExecuteResult(output=f"{self.label}:{command}", exit_code=0, truncated=False)

        provider = RuntimeBackendResolver(default_runtime="sandbox_1")
        provider.register_runtime("local", FakeBackend("local"))
        provider.register_runtime("sandbox_1", FakeBackend("sandbox"))

        execute_tool = next(t for t in get_client_tools_with_runtime(provider) if t.name == "execute")

        # explicit routing to sandbox_1
        res = execute_tool.invoke({"command": "echo test", "target_runtime": "sandbox_1"})
        assert "sandbox:echo test" in res

        # explicit routing
        res = execute_tool.invoke({"command": "echo test", "target_runtime": "local"})
        assert "local:echo test" in res

    def test_invalid_runtime_returns_error_string(self):
        class FakeBackend:
            def execute(self, command: str) -> ExecuteResult:
                return ExecuteResult(output=command, exit_code=0, truncated=False)

        provider = RuntimeBackendResolver(default_runtime="local")
        provider.register_runtime("local", FakeBackend())
        provider.register_runtime("sandbox_1", FakeBackend())

        execute_tool = next(t for t in get_client_tools_with_runtime(provider) if t.name == "execute")
        res = execute_tool.invoke({"command": "echo test", "target_runtime": "nope"})

        assert "Unknown runtime" in res
        assert "Available runtimes" in res
        assert "local" in res
        assert "sandbox_1" in res


class TestLsToolGenerator:
    """Test get_ls_tool function."""

    def testget_ls_tool_creates_tool(self):
        """Test that ls tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_ls_tool(provider)

            assert tool.name == "ls"
            assert "列出目录中的所有文件" in tool.description

    def test_ls_tool_with_custom_description(self):
        """Test ls tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            custom_desc = "Custom ls description"
            tool = get_ls_tool(provider, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_ls_tool_execution(self):
        """Test executing ls tool."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").write_text("content1")
            (tmppath / "file2.py").write_text("content2")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            provider = _local_provider(backend)
            tool = get_ls_tool(provider)

            result = tool.invoke({"path": "/", "target_runtime": "local"})

            assert "file1.txt" in result
            assert "file2.py" in result

    def test_ls_tool_with_virtual_mode(self):
        """Test ls tool in virtual mode."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.txt").write_text("content")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            provider = _local_provider(backend)
            tool = get_ls_tool(provider)

            result = tool.invoke({"path": "/", "target_runtime": "local"})

            assert "/test.txt" in result


class TestReadFileToolGenerator:
    """Test get_read_file_tool function."""

    def testget_read_file_tool_creates_tool(self):
        """Test that read_file tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_read_file_tool(provider)

            assert tool.name == "read_file"
            assert "从文件系统读取文件" in tool.description

    def test_read_file_with_custom_description(self):
        """Test read_file tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            custom_desc = "Custom read description"
            tool = get_read_file_tool(provider, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_read_file_execution(self):
        """Test executing read_file tool."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("line1\nline2\nline3")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            provider = _local_provider(backend)
            tool = get_read_file_tool(provider)

            result = tool.invoke({"file_path": "/test.txt", "target_runtime": "local"})

            assert "line1" in result
            assert "line2" in result
            assert "line3" in result

    def test_read_file_with_offset_and_limit(self):
        """Test read_file tool with offset and limit parameters."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("line1\nline2\nline3\nline4\nline5")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            provider = _local_provider(backend)
            tool = get_read_file_tool(provider)

            result = tool.invoke({"file_path": "/test.txt", "target_runtime": "local", "offset": 2, "limit": 2})

            assert "line3" in result
            assert "line4" in result
            assert "line1" not in result
            assert "line5" not in result

    def test_read_file_defaults(self):
        """Test read_file tool default parameters."""
        assert DEFAULT_READ_OFFSET == 0
        assert DEFAULT_READ_LIMIT == 100


class TestWriteFileToolGenerator:
    """Test get_write_file_tool function."""

    def testget_write_file_tool_creates_tool(self):
        """Test that write_file tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_write_file_tool(provider)

            assert tool.name == "write_file"
            assert "在文件系统中新建文件" in tool.description

    def test_write_file_with_custom_description(self):
        """Test write_file tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            custom_desc = "Custom write description"
            tool = get_write_file_tool(provider, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_write_file_execution(self):
        """Test executing write_file tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            provider = _local_provider(backend)
            tool = get_write_file_tool(provider)

            result = tool.invoke({"file_path": "/test.txt", "content": "test content", "target_runtime": "local"})

            assert "Updated file /test.txt" in result or "Updated file test.txt" in result
            assert (Path(tmpdir) / "test.txt").read_text() == "test content"

    def test_write_file_existing_file(self):
        """Test write_file tool on existing file."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.txt").write_text("old content")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            provider = _local_provider(backend)
            tool = get_write_file_tool(provider)

            result = tool.invoke({"file_path": "/test.txt", "content": "new content", "target_runtime": "local"})

            assert "already exists" in result.lower()
            assert (Path(tmpdir) / "test.txt").read_text() == "old content"


class TestEditFileToolGenerator:
    """Test get_edit_file_tool function."""

    def testget_edit_file_tool_creates_tool(self):
        """Test that edit_file tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_edit_file_tool(provider)

            assert tool.name == "edit_file"
            assert "精确字符串替换" in tool.description

    def test_edit_file_with_custom_description(self):
        """Test edit_file tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            custom_desc = "Custom edit description"
            tool = get_edit_file_tool(provider, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_edit_file_execution(self):
        """Test executing edit_file tool."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("hello world\nhello python")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            provider = _local_provider(backend)
            tool = get_edit_file_tool(provider)

            result = tool.invoke(
                {
                    "file_path": "/test.txt",
                    "old_string": "world",
                    "new_string": "universe",
                    "target_runtime": "local",
                }
            )

            assert "replaced" in result.lower()
            assert test_file.read_text() == "hello universe\nhello python"

    def test_edit_file_replace_all(self):
        """Test edit_file tool with replace_all=True."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("hello world\nhello python")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            provider = _local_provider(backend)
            tool = get_edit_file_tool(provider)

            result = tool.invoke(
                {
                    "file_path": "/test.txt",
                    "old_string": "hello",
                    "new_string": "hi",
                    "replace_all": True,
                    "target_runtime": "local",
                }
            )

            assert "2" in result  # 2 occurrences replaced
            assert test_file.read_text() == "hi world\nhi python"


class TestGlobToolGenerator:
    """Test get_glob_tool function."""

    def testget_glob_tool_creates_tool(self):
        """Test that glob tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_glob_tool(provider)

            assert tool.name == "glob"
            assert "按 glob 模式查找文件" in tool.description

    def test_glob_with_custom_description(self):
        """Test glob tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            custom_desc = "Custom glob description"
            tool = get_glob_tool(provider, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_glob_execution(self):
        """Test executing glob tool."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").write_text("content1")
            (tmppath / "file2.txt").write_text("content2")
            (tmppath / "script.py").write_text("content3")

            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_glob_tool(provider)

            result = tool.invoke({"pattern": "*.txt", "target_runtime": "local"})

            assert "file1.txt" in result
            assert "file2.txt" in result
            assert ".py" not in result

    def test_glob_with_path_parameter(self):
        """Test glob tool with path parameter."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file.txt").write_text("content")
            (tmppath / "subdir").mkdir()
            (tmppath / "subdir" / "nested.txt").write_text("nested")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            provider = _local_provider(backend)
            tool = get_glob_tool(provider)

            result = tool.invoke({"pattern": "*.txt", "target_runtime": "local", "path": "/subdir"})

            assert "nested.txt" in result


class TestGrepToolGenerator:
    """Test get_grep_tool function."""

    def testget_grep_tool_creates_tool(self):
        """Test that grep tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_grep_tool(provider)

            assert tool.name == "grep"
            assert "搜索文本模式" in tool.description

    def test_grep_with_custom_description(self):
        """Test grep tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            custom_desc = "Custom grep description"
            tool = get_grep_tool(provider, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_grep_execution(self):
        """Test executing grep tool."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").write_text("hello world\nhello python")
            (tmppath / "file2.txt").write_text("goodbye world")

            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_grep_tool(provider)

            result = tool.invoke({"pattern": "hello", "target_runtime": "local"})

            assert "file1.txt" in result

    def test_grep_with_glob_filter(self):
        """Test grep tool with glob filter."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.py").write_text("import os")
            (tmppath / "test.txt").write_text("import os")

            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_grep_tool(provider)

            result = tool.invoke({"pattern": "import", "target_runtime": "local", "glob": "*.py"})

            assert ".py" in result
            assert ".txt" not in result

    def test_grep_content_mode(self):
        """Test grep tool with content output mode."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file.txt").write_text("line1\nline2")

            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_grep_tool(provider)

            result = tool.invoke({"pattern": "line", "target_runtime": "local", "output_mode": "content"})

            assert "line1" in result or "line2" in result


class TestExecuteToolGenerator:
    """Test get_execute_tool function."""

    def testget_execute_tool_creates_tool(self):
        """Test that execute tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_execute_tool(provider)

            assert tool.name == "execute"
            assert "执行 shell 命令" in tool.description

    def test_execute_with_custom_description(self):
        """Test execute tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            custom_desc = "Custom execute description"
            tool = get_execute_tool(provider, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_execute_execution(self):
        """Test executing execute tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_execute_tool(provider)

            result = tool.invoke({"command": "echo test", "target_runtime": "local"})

            assert "test" in result

    @pytest.mark.asyncio
    async def test_execute_async_execution(self):
        """Test async execution of execute tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_execute_tool(provider)

            result = await tool.ainvoke({"command": "echo test", "target_runtime": "local"})

            assert "test" in result


class TestExecuteToolSecurity:
    """Test get_execute_tool security functionality."""

    def test_execute_with_enable_security_none_default_enabled(self):
        """测试 enable_security=None 时默认启用校验（危险命令被拒绝）"""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            # enable_security=None 是默认值，应该启用安全校验
            tool = get_execute_tool(provider, enable_security=None)

            # rm 是危险命令，不在白名单中，应被拒绝
            result = tool.invoke({"command": "rm -rf /some/path", "target_runtime": "local"})
            assert "命令执行被拒绝" in result

    def test_execute_with_enable_security_true(self):
        """测试 enable_security=True 时启用校验（危险命令被拒绝）"""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_execute_tool(provider, enable_security=True)

            # rm 是危险命令，不在白名单中，应被拒绝
            result = tool.invoke({"command": "rm -rf /some/path", "target_runtime": "local"})
            assert "命令执行被拒绝" in result

    def test_execute_with_enable_security_false(self):
        """测试 enable_security=False 时禁用校验（危险命令可执行）"""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_execute_tool(provider, enable_security=False)

            # 即使是危险命令，禁用安全校验后也应执行
            result = tool.invoke({"command": "echo dangerous_test", "target_runtime": "local"})
            assert "dangerous_test" in result

    def test_execute_allowed_command_with_security_enabled(self):
        """测试启用安全校验时，白名单命令可正常执行"""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_execute_tool(provider, enable_security=True)

            # ls 是白名单命令，应正常执行
            result = tool.invoke({"command": "ls -la", "target_runtime": "local"})
            assert "命令执行被拒绝" not in result

    @pytest.mark.asyncio
    async def test_execute_async_with_security_enabled(self):
        """测试异步执行时安全校验同样生效"""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_execute_tool(provider, enable_security=True)

            # 危险命令在异步执行时也应被拒绝
            result = await tool.ainvoke({"command": "rm -rf /", "target_runtime": "local"})
            assert "命令执行被拒绝" in result

    @pytest.mark.asyncio
    async def test_execute_async_with_security_disabled(self):
        """测试异步执行时禁用安全校验"""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tool = get_execute_tool(provider, enable_security=False)

            # 禁用安全校验后异步执行也应正常
            result = await tool.ainvoke({"command": "echo async_test", "target_runtime": "local"})
            assert "async_test" in result


class TestGetClientToolsWithRuntimeSecurity:
    """Test get_client_tools_with_runtime security parameter."""

    def test_get_client_tools_with_runtime_security_none(self):
        """测试 get_client_tools_with_runtime 默认启用安全校验"""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tools = get_client_tools_with_runtime(provider, enable_security=None)

            execute_tool = next(t for t in tools if t.name == "execute")
            # 危险命令应被拒绝
            result = execute_tool.invoke({"command": "rm -rf /", "target_runtime": "local"})
            assert "命令执行被拒绝" in result

    def test_get_client_tools_with_runtime_security_true(self):
        """测试 get_client_tools_with_runtime enable_security=True 启用校验"""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tools = get_client_tools_with_runtime(provider, enable_security=True)

            execute_tool = next(t for t in tools if t.name == "execute")
            # 危险命令应被拒绝
            result = execute_tool.invoke({"command": "rm -rf /", "target_runtime": "local"})
            assert "命令执行被拒绝" in result

    def test_get_client_tools_with_runtime_security_false(self):
        """测试 get_client_tools_with_runtime enable_security=False 禁用校验"""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tools = get_client_tools_with_runtime(provider, enable_security=False)

            execute_tool = next(t for t in tools if t.name == "execute")
            # 禁用安全校验后命令可执行
            result = execute_tool.invoke({"command": "echo no_security_check", "target_runtime": "local"})
            assert "no_security_check" in result

    def test_get_client_tools_with_runtime_returns_seven_tools(self):
        """测试 get_client_tools_with_runtime 返回 7 个工具"""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            provider = _local_provider(backend)
            tools = get_client_tools_with_runtime(provider)

            tool_names = {t.name for t in tools}
            expected_names = {"ls", "read_file", "write_file", "edit_file", "glob", "grep", "execute"}
            assert tool_names == expected_names


class TestToolIntegration:
    """Integration tests for tools working together."""

    def test_write_then_read_flow(self):
        """Test write file followed by read file workflow."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            tools = get_client_tools_with_runtime(_local_provider(backend))

            write_tool = next(t for t in tools if t.name == "write_file")
            read_tool = next(t for t in tools if t.name == "read_file")

            write_tool.invoke({"file_path": "/test.txt", "content": "hello world", "target_runtime": "local"})
            result = read_tool.invoke({"file_path": "/test.txt", "target_runtime": "local"})

            assert "hello world" in result

    def test_ls_glob_and_grep_flow(self):
        """Test using ls, glob, and grep together."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test1.txt").write_text("import os")
            (tmppath / "test2.txt").write_text("import sys")
            (tmppath / "main.py").write_text("print('hello')")

            backend = FilesystemBackend(root_dir=tmpdir)
            tools = get_client_tools_with_runtime(_local_provider(backend))

            ls_tool = next(t for t in tools if t.name == "ls")
            glob_tool = next(t for t in tools if t.name == "glob")
            grep_tool = next(t for t in tools if t.name == "grep")

            ls_result = ls_tool.invoke({"path": "/", "target_runtime": "local"})
            assert len(ls_result) > 0

            glob_result = glob_tool.invoke({"pattern": "*.py", "target_runtime": "local"})
            assert ".py" in glob_result

            grep_result = grep_tool.invoke({"pattern": "import", "target_runtime": "local"})
            assert "txt" in grep_result or "test" in grep_result

    def test_write_edit_read_flow(self):
        """Test write, edit, and read workflow."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            tools = get_client_tools_with_runtime(_local_provider(backend))

            write_tool = next(t for t in tools if t.name == "write_file")
            edit_tool = next(t for t in tools if t.name == "edit_file")
            read_tool = next(t for t in tools if t.name == "read_file")

            write_tool.invoke(
                {"file_path": "/test.txt", "content": "hello world\nhello python", "target_runtime": "local"}
            )
            edit_tool.invoke(
                {"file_path": "/test.txt", "old_string": "world", "new_string": "universe", "target_runtime": "local"}
            )
            result = read_tool.invoke({"file_path": "/test.txt", "target_runtime": "local"})

            assert "hello universe" in result
            assert "hello python" in result
