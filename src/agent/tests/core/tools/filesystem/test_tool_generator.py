# -*- coding: utf-8 -*-
"""
Test module for tool_generator.

This module contains tests for filesystem tool generators.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from aidev_agent.core.tools.filesystem.backend import FilesystemBackend
from aidev_agent.core.tools.filesystem.tool_generator import (
    DEFAULT_READ_LIMIT,
    DEFAULT_READ_OFFSET,
    _edit_file_tool_generator,
    _execute_tool_generator,
    _glob_tool_generator,
    _grep_tool_generator,
    _ls_tool_generator,
    _read_file_tool_generator,
    _validate_path,
    _write_file_tool_generator,
    get_filesystem_tools,
)


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
        # _validate_path only checks if path contains ~ or starts with ~
        # ~/.bashrc starts with ~ so it will be rejected
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


class TestLsToolGenerator:
    """Test _ls_tool_generator function."""

    def test_ls_tool_generator_creates_tool(self):
        """Test that ls tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _ls_tool_generator(backend)

            assert tool.name == "ls"
            assert "Lists all files in a directory" in tool.description

    def test_ls_tool_with_custom_description(self):
        """Test ls tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            custom_desc = "Custom ls description"
            tool = _ls_tool_generator(backend, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_ls_tool_execution(self):
        """Test executing ls tool."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").write_text("content1")
            (tmppath / "file2.py").write_text("content2")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            tool = _ls_tool_generator(backend)

            result = tool.invoke({"path": "/"})

            assert "file1.txt" in result
            assert "file2.py" in result

    def test_ls_tool_with_virtual_mode(self):
        """Test ls tool in virtual mode."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.txt").write_text("content")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            tool = _ls_tool_generator(backend)

            result = tool.invoke({"path": "/"})

            assert "/test.txt" in result


class TestReadFileToolGenerator:
    """Test _read_file_tool_generator function."""

    def test_read_file_tool_generator_creates_tool(self):
        """Test that read_file tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _read_file_tool_generator(backend)

            assert tool.name == "read_file"
            assert "Reads a file" in tool.description

    def test_read_file_with_custom_description(self):
        """Test read_file tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            custom_desc = "Custom read description"
            tool = _read_file_tool_generator(backend, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_read_file_execution(self):
        """Test executing read_file tool."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("line1\nline2\nline3")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            tool = _read_file_tool_generator(backend)

            result = tool.invoke({"file_path": "/test.txt"})

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
            tool = _read_file_tool_generator(backend)

            result = tool.invoke({"file_path": "/test.txt", "offset": 2, "limit": 2})

            assert "line3" in result
            assert "line4" in result
            assert "line1" not in result
            assert "line5" not in result

    def test_read_file_defaults(self):
        """Test read_file tool default parameters."""
        assert DEFAULT_READ_OFFSET == 0
        assert DEFAULT_READ_LIMIT == 100


class TestWriteFileToolGenerator:
    """Test _write_file_tool_generator function."""

    def test_write_file_tool_generator_creates_tool(self):
        """Test that write_file tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _write_file_tool_generator(backend)

            assert tool.name == "write_file"
            assert "Writes to a new file" in tool.description

    def test_write_file_with_custom_description(self):
        """Test write_file tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            custom_desc = "Custom write description"
            tool = _write_file_tool_generator(backend, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_write_file_execution(self):
        """Test executing write_file tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            tool = _write_file_tool_generator(backend)

            result = tool.invoke({"file_path": "/test.txt", "content": "test content"})

            assert "Updated file /test.txt" in result or "Updated file test.txt" in result
            assert (Path(tmpdir) / "test.txt").read_text() == "test content"

    def test_write_file_existing_file(self):
        """Test write_file tool on existing file."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.txt").write_text("old content")

            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _write_file_tool_generator(backend)

            result = tool.invoke({"file_path": "/test.txt", "content": "new content"})

            assert "already exists" in result.lower()
            assert (Path(tmpdir) / "test.txt").read_text() == "old content"


class TestEditFileToolGenerator:
    """Test _edit_file_tool_generator function."""

    def test_edit_file_tool_generator_creates_tool(self):
        """Test that edit_file tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _edit_file_tool_generator(backend)

            assert tool.name == "edit_file"
            assert "Performs exact string replacements" in tool.description

    def test_edit_file_with_custom_description(self):
        """Test edit_file tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            custom_desc = "Custom edit description"
            tool = _edit_file_tool_generator(backend, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_edit_file_execution(self):
        """Test executing edit_file tool."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("hello world\nhello python")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            tool = _edit_file_tool_generator(backend)

            result = tool.invoke(
                {
                    "file_path": "/test.txt",
                    "old_string": "world",
                    "new_string": "universe",
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
            tool = _edit_file_tool_generator(backend)

            result = tool.invoke(
                {
                    "file_path": "/test.txt",
                    "old_string": "hello",
                    "new_string": "hi",
                    "replace_all": True,
                }
            )

            assert "2" in result  # 2 occurrences replaced
            assert test_file.read_text() == "hi world\nhi python"


class TestGlobToolGenerator:
    """Test _glob_tool_generator function."""

    def test_glob_tool_generator_creates_tool(self):
        """Test that glob tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _glob_tool_generator(backend)

            assert tool.name == "glob"
            assert "Find files matching a glob pattern" in tool.description

    def test_glob_with_custom_description(self):
        """Test glob tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            custom_desc = "Custom glob description"
            tool = _glob_tool_generator(backend, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_glob_execution(self):
        """Test executing glob tool."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").write_text("content1")
            (tmppath / "file2.txt").write_text("content2")
            (tmppath / "script.py").write_text("content3")

            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _glob_tool_generator(backend)

            result = tool.invoke({"pattern": "*.txt"})

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
            tool = _glob_tool_generator(backend)

            result = tool.invoke({"pattern": "*.txt", "path": "/subdir"})

            assert "nested.txt" in result


class TestGrepToolGenerator:
    """Test _grep_tool_generator function."""

    def test_grep_tool_generator_creates_tool(self):
        """Test that grep tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _grep_tool_generator(backend)

            assert tool.name == "grep"
            assert "Search for a text pattern" in tool.description

    def test_grep_with_custom_description(self):
        """Test grep tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            custom_desc = "Custom grep description"
            tool = _grep_tool_generator(backend, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_grep_execution(self):
        """Test executing grep tool."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").write_text("hello world\nhello python")
            (tmppath / "file2.txt").write_text("goodbye world")

            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _grep_tool_generator(backend)

            result = tool.invoke({"pattern": "hello"})

            assert "file1.txt" in result

    def test_grep_with_glob_filter(self):
        """Test grep tool with glob filter."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.py").write_text("import os")
            (tmppath / "test.txt").write_text("import os")

            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _grep_tool_generator(backend)

            result = tool.invoke({"pattern": "import", "glob": "*.py"})

            assert ".py" in result
            assert ".txt" not in result

    def test_grep_content_mode(self):
        """Test grep tool with content output mode."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file.txt").write_text("line1\nline2")

            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _grep_tool_generator(backend)

            result = tool.invoke({"pattern": "line", "output_mode": "content"})

            assert "line1" in result or "line2" in result


class TestExecuteToolGenerator:
    """Test _execute_tool_generator function."""

    def test_execute_tool_generator_creates_tool(self):
        """Test that execute tool generator creates a valid tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _execute_tool_generator(backend)

            assert tool.name == "execute"
            assert "Executes a shell command" in tool.description

    def test_execute_with_custom_description(self):
        """Test execute tool with custom description."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            custom_desc = "Custom execute description"
            tool = _execute_tool_generator(backend, custom_description=custom_desc)

            assert tool.description == custom_desc

    def test_execute_execution(self):
        """Test executing execute tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _execute_tool_generator(backend)

            result = tool.invoke({"command": "echo test"})

            assert "test" in result
            assert "succeeded" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_async_execution(self):
        """Test async execution of execute tool."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            tool = _execute_tool_generator(backend)

            result = await tool.ainvoke({"command": "echo test"})

            assert "test" in result
            assert "succeeded" in result.lower()


class TestGetFilesystemTools:
    """Test get_filesystem_tools factory function."""

    def test_get_filesystem_tools_default(self):
        """Test get_filesystem_tools with default backend."""
        tools = get_filesystem_tools()

        tool_names = [t.name for t in tools]
        assert "ls" in tool_names
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "edit_file" in tool_names
        assert "glob" in tool_names
        assert "grep" in tool_names
        assert "execute" in tool_names

    def test_get_filesystem_tools_with_custom_backend(self):
        """Test get_filesystem_tools with custom backend."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            tools = get_filesystem_tools(backend=backend)

            assert len(tools) > 0
            for tool in tools:
                # All tools should use the provided backend
                assert hasattr(tool, "name")

    def test_get_filesystem_tools_with_custom_descriptions(self):
        """Test get_filesystem_tools with custom descriptions."""
        custom_descriptions = {
            "ls": "Custom ls description",
            "read_file": "Custom read description",
        }

        tools = get_filesystem_tools(custom_tool_descriptions=custom_descriptions)

        ls_tool = next(t for t in tools if t.name == "ls")
        read_tool = next(t for t in tools if t.name == "read_file")

        assert ls_tool.description == "Custom ls description"
        assert read_tool.description == "Custom read description"

    def test_get_filesystem_tools_returns_all_tools(self):
        """Test that get_filesystem_tools returns all expected tools."""
        tools = get_filesystem_tools()

        expected_tools = {
            "ls",
            "read_file",
            "write_file",
            "edit_file",
            "glob",
            "grep",
            "execute",
        }

        actual_tools = {t.name for t in tools}
        assert actual_tools == expected_tools


class TestToolIntegration:
    """Integration tests for tools working together."""

    def test_write_then_read_flow(self):
        """Test write file followed by read file workflow."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            tools = get_filesystem_tools(backend=backend)

            write_tool = next(t for t in tools if t.name == "write_file")
            read_tool = next(t for t in tools if t.name == "read_file")

            # Write a file
            write_tool.invoke({"file_path": "/test.txt", "content": "hello world"})

            # Read it back
            result = read_tool.invoke({"file_path": "/test.txt"})

            assert "hello world" in result

    def test_ls_glob_and_grep_flow(self):
        """Test using ls, glob, and grep together."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test1.txt").write_text("import os")
            (tmppath / "test2.txt").write_text("import sys")
            (tmppath / "main.py").write_text("print('hello')")

            backend = FilesystemBackend(root_dir=tmpdir)
            tools = get_filesystem_tools(backend=backend)

            ls_tool = next(t for t in tools if t.name == "ls")
            glob_tool = next(t for t in tools if t.name == "glob")
            grep_tool = next(t for t in tools if t.name == "grep")

            # List files
            ls_result = ls_tool.invoke({"path": "/"})
            assert len(ls_result) > 0

            # Find Python files
            glob_result = glob_tool.invoke({"pattern": "*.py"})
            assert ".py" in glob_result

            # Search for import
            grep_result = grep_tool.invoke({"pattern": "import"})
            assert "txt" in grep_result or "test" in grep_result

    def test_write_edit_read_flow(self):
        """Test write, edit, and read workflow."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            tools = get_filesystem_tools(backend=backend)

            write_tool = next(t for t in tools if t.name == "write_file")
            edit_tool = next(t for t in tools if t.name == "edit_file")
            read_tool = next(t for t in tools if t.name == "read_file")

            # Write initial content
            write_tool.invoke({"file_path": "/test.txt", "content": "hello world\nhello python"})

            # Edit the file
            edit_tool.invoke({"file_path": "/test.txt", "old_string": "world", "new_string": "universe"})

            # Read and verify
            result = read_tool.invoke({"file_path": "/test.txt"})

            assert "hello universe" in result
            assert "hello python" in result
