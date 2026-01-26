# -*- coding: utf-8 -*-
"""
Test module for FilesystemBackend.

This module contains tests for the FilesystemBackend class which provides
direct file system read/write operations.
"""

from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir

import pytest
from aidev_agent.core.tools.filesystem.backend import (
    EditResult,
    ExecuteResult,
    FilesystemBackend,
    WriteResult,
)


class TestFilesystemBackendInitialization:
    """Test FilesystemBackend initialization."""

    def test_init_default(self):
        """Test initialization with default parameters."""
        backend = FilesystemBackend()
        assert backend.virtual_mode is False
        assert backend.max_file_size_bytes == 10 * 1024 * 1024  # 10 MB
        assert backend.cwd.exists()

    def test_init_with_root_dir(self):
        """Test initialization with custom root directory."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            assert backend.cwd == Path(tmpdir).resolve()

    def test_init_with_virtual_mode(self):
        """Test initialization with virtual mode enabled."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            assert backend.virtual_mode is True

    def test_init_with_custom_max_file_size(self):
        """Test initialization with custom max file size."""
        backend = FilesystemBackend(max_file_size_mb=5)
        assert backend.max_file_size_bytes == 5 * 1024 * 1024


class TestFilesystemBackendResolvePath:
    """Test path resolution in FilesystemBackend."""

    def test_resolve_path_absolute_non_virtual(self):
        """Test resolving absolute path in non-virtual mode."""
        backend = FilesystemBackend()
        # 使用 gettempdir() 获取系统临时目录，提高可移植性
        temp_dir = gettempdir()
        path = backend._resolve_path(temp_dir)
        assert path.exists() or path == Path(temp_dir)

    def test_resolve_path_relative_non_virtual(self):
        """Test resolving relative path in non-virtual mode."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            (Path(tmpdir) / "test_file.txt").write_text("test")
            path = backend._resolve_path("test_file.txt")
            assert path == (Path(tmpdir) / "test_file.txt").resolve()

    def test_resolve_path_virtual_mode_simple(self):
        """Test resolving simple path in virtual mode."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            path = backend._resolve_path("test.txt")
            assert path == (Path(tmpdir) / "test.txt").resolve()
            assert path.parent == backend.cwd

    def test_resolve_path_virtual_mode_with_leading_slash(self):
        """Test resolving path with leading slash in virtual mode."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            path = backend._resolve_path("/test.txt")
            assert path == (Path(tmpdir) / "test.txt").resolve()

    def test_resolve_path_virtual_mode_prevents_traversal(self):
        """Test that virtual mode prevents path traversal."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            with pytest.raises(ValueError, match="不允许路径遍历"):
                backend._resolve_path("../etc/passwd")

    def test_resolve_path_virtual_mode_prevents_escape(self):
        """Test that virtual mode prevents escaping root directory."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            with pytest.raises(ValueError, match="不允许路径遍历"):
                backend._resolve_path("../../../etc/passwd")


class TestFilesystemBackendLsInfo:
    """Test ls_info method."""

    def test_ls_info_non_existent_directory(self):
        """Test ls_info on non-existent directory."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.ls_info("/nonexistent")
            assert result == []

    def test_ls_info_empty_directory(self):
        """Test ls_info on empty directory."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            # 空目录应该返回空列表
            result = backend.ls_info(".")
            assert len(result) == 0

    def test_ls_info_with_files(self):
        """Test ls_info with files and directories."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").write_text("content1")
            (tmppath / "file2.py").write_text("content2")
            (tmppath / "subdir").mkdir()
            (tmppath / "subdir" / "nested.txt").write_text("nested")

            backend = FilesystemBackend(root_dir=tmpdir)
            results = backend.ls_info(".")

            paths = [r["path"] for r in results]
            assert len(results) == 3
            assert any("file1.txt" in p for p in paths)
            assert any("file2.py" in p for p in paths)
            assert any("subdir" in p for p in paths)

    def test_ls_info_virtual_mode(self):
        """Test ls_info in virtual mode returns virtual paths."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.txt").write_text("content")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            results = backend.ls_info("/")

            assert len(results) == 1
            assert results[0]["path"] == "/test.txt"


class TestFilesystemBackendRead:
    """Test read method."""

    def test_read_non_existent_file(self):
        """Test reading non-existent file."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.read("/nonexistent.txt")
            assert "not found" in result.lower()

    def test_read_file_success(self):
        """Test reading existing file."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("line1\nline2\nline3")

            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.read("test.txt")

            assert "     1\tline1" in result
            assert "     2\tline2" in result
            assert "     3\tline3" in result

    def test_read_with_offset(self):
        """Test reading file with offset."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("line1\nline2\nline3\nline4")

            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.read("test.txt", offset=2, limit=2)

            assert "     3\tline3" in result
            assert "     4\tline4" in result
            assert "line1" not in result

    def test_read_with_limit(self):
        """Test reading file with limit."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("line1\nline2\nline3\nline4\nline5")

            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.read("test.txt", limit=3)

            assert "     1\tline1" in result
            assert "     2\tline2" in result
            assert "     3\tline3" in result
            assert "line4" not in result

    def test_read_empty_file(self):
        """Test reading empty file."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "empty.txt"
            test_file.write_text("")

            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.read("empty.txt")

            assert "文件存在但内容为空" in result


class TestFilesystemBackendWrite:
    """Test write method."""

    def test_write_new_file(self):
        """Test writing to a new file."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.write("new_file.txt", "test content")

            assert isinstance(result, WriteResult)
            assert result.error is None
            assert result.path == "new_file.txt"
            assert (Path(tmpdir) / "new_file.txt").read_text() == "test content"

    def test_write_existing_file_fails(self):
        """Test that writing to existing file fails."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "existing.txt").write_text("old content")

            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.write("existing.txt", "new content")

            assert isinstance(result, WriteResult)
            assert result.error is not None
            assert "already exists" in result.error

    def test_write_creates_parent_directories(self):
        """Test that write creates parent directories."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.write("subdir/nested/file.txt", "content")

            assert result.error is None
            assert (Path(tmpdir) / "subdir" / "nested" / "file.txt").exists()

    def test_write_virtual_mode_path_traversal(self):
        """Test that write in virtual mode prevents path traversal."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            result = backend.write("../escape.txt", "content")

            assert result.error is not None


class TestFilesystemBackendEdit:
    """Test edit method."""

    def test_edit_non_existent_file(self):
        """Test editing non-existent file."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.edit("nonexistent.txt", "old", "new")

            assert isinstance(result, EditResult)
            assert result.error is not None
            assert "not found" in result.error.lower()

    def test_edit_single_occurrence(self):
        """Test editing single occurrence."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("hello world\nhello python")

            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.edit("test.txt", "world", "universe")

            assert isinstance(result, EditResult)
            assert result.error is None
            assert result.occurrences == 1
            assert test_file.read_text() == "hello universe\nhello python"

    def test_edit_replace_all(self):
        """Test editing with replace_all=True."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("hello world\nhello python\nhello there")

            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.edit("test.txt", "hello", "hi", replace_all=True)

            assert isinstance(result, EditResult)
            assert result.error is None
            assert result.occurrences == 3
            assert test_file.read_text() == "hi world\nhi python\nhi there"

    def test_edit_multiple_occurrences_without_replace_all(self):
        """Test that editing multiple occurrences without replace_all fails."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.txt"
            test_file.write_text("hello world\nhello python")

            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.edit("test.txt", "hello", "hi", replace_all=False)

            assert isinstance(result, EditResult)
            assert result.error is not None
            assert "匹配" in result.error or "occurrences" in result.error.lower()


class TestFilesystemBackendGrep:
    """Test grep methods."""

    def test_grep_raw_simple_pattern(self):
        """Test grep with simple pattern."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").write_text("hello world\nhello python")
            (tmppath / "file2.txt").write_text("goodbye world")

            backend = FilesystemBackend(root_dir=tmpdir)
            results = backend.grep_raw("hello")

            assert len(results) > 0
            assert any(r["text"] == "hello world" for r in results)
            assert any(r["text"] == "hello python" for r in results)

    def test_grep_raw_invalid_regex(self):
        """Test grep with invalid regex pattern."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.grep_raw("[invalid(regex")

            assert isinstance(result, str)
            assert "Invalid regex" in result

    def test_grep_raw_with_glob(self):
        """Test grep with glob filter."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.py").write_text("import os")
            (tmppath / "test.txt").write_text("import os")

            backend = FilesystemBackend(root_dir=tmpdir)
            results = backend.grep_raw("import", glob="*.py")

            assert len(results) == 1
            assert ".py" in results[0]["path"]


class TestFilesystemBackendGlob:
    """Test glob_info method."""

    def test_glob_info_simple_pattern(self):
        """Test glob with simple pattern."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").write_text("content1")
            (tmppath / "file2.txt").write_text("content2")
            (tmppath / "script.py").write_text("content3")

            backend = FilesystemBackend(root_dir=tmpdir)
            results = backend.glob_info("*.txt")

            assert len(results) == 2
            assert all(".txt" in r["path"] for r in results)

    def test_glob_info_recursive_pattern(self):
        """Test glob with recursive pattern."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").write_text("content1")
            (tmppath / "subdir").mkdir()
            (tmppath / "subdir" / "file2.txt").write_text("content2")

            backend = FilesystemBackend(root_dir=tmpdir)
            results = backend.glob_info("**/*.txt")

            assert len(results) == 2

    def test_glob_info_virtual_mode(self):
        """Test glob in virtual mode returns virtual paths."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.txt").write_text("content")

            backend = FilesystemBackend(root_dir=tmpdir, virtual_mode=True)
            results = backend.glob_info("*.txt")

            assert len(results) == 1
            assert results[0]["path"] == "/test.txt"


class TestFilesystemBackendUploadDownload:
    """Test upload_files and download_files methods."""

    def test_upload_files_single(self):
        """Test uploading a single file."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            files = [("test.txt", b"test content")]

            results = backend.upload_files(files)

            assert len(results) == 1
            assert results[0]["path"] == "test.txt"
            assert results[0]["error"] is None
            assert (Path(tmpdir) / "test.txt").read_bytes() == b"test content"

    def test_upload_files_multiple(self):
        """Test uploading multiple files."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            files = [
                ("file1.txt", b"content1"),
                ("file2.txt", b"content2"),
                ("subdir/file3.txt", b"content3"),
            ]

            results = backend.upload_files(files)

            assert len(results) == 3
            assert all(r["error"] is None for r in results)

    def test_download_files_single(self):
        """Test downloading a single file."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.txt").write_bytes(b"test content")

            backend = FilesystemBackend(root_dir=tmpdir)
            results = backend.download_files(["test.txt"])

            assert len(results) == 1
            assert results[0]["path"] == "test.txt"
            assert results[0]["error"] is None
            assert results[0]["content"] == b"test content"

    def test_download_files_non_existent(self):
        """Test downloading non-existent file."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            results = backend.download_files(["nonexistent.txt"])

            assert len(results) == 1
            assert results[0]["error"] == "file_not_found"


class TestFilesystemBackendExecute:
    """Test execute method."""

    def test_execute_simple_command(self):
        """Test executing a simple command."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.execute("echo hello")

            assert isinstance(result, ExecuteResult)
            assert "hello" in result.output
            assert result.exit_code == 0

    def test_execute_with_timeout(self):
        """Test executing a command with timeout."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.execute("echo test", timeout=10)

            assert result.exit_code == 0

    def test_execute_non_existent_command(self):
        """Test executing a non-existent command."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            result = backend.execute("nonexistentcommand12345")

            assert isinstance(result, ExecuteResult)
            assert result.exit_code is not None
            assert result.exit_code != 0


class TestFilesystemBackendAexecute:
    """Test aexecute (async execute) method."""

    @pytest.mark.asyncio
    async def test_aexecute_simple_command(self):
        """Test async execution of a simple command."""
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)
            result = await backend.aexecute("echo hello")

            assert isinstance(result, ExecuteResult)
            assert "hello" in result.output
            assert result.exit_code == 0


class TestDataClasses:
    """Test data classes (WriteResult, EditResult, ExecuteResult, etc.)."""

    def test_write_result_success(self):
        """Test WriteResult on success."""
        result = WriteResult(path="test.txt")
        assert result.path == "test.txt"
        assert result.error is None
        assert result.files_update is None

    def test_write_result_error(self):
        """Test WriteResult on error."""
        result = WriteResult(error="File exists")
        assert result.path is None
        assert result.error == "File exists"

    def test_edit_result_success(self):
        """Test EditResult on success."""
        result = EditResult(path="test.txt", occurrences=5)
        assert result.path == "test.txt"
        assert result.occurrences == 5
        assert result.error is None

    def test_edit_result_error(self):
        """Test EditResult on error."""
        result = EditResult(error="File not found")
        assert result.error == "File not found"
        assert result.occurrences is None

    def test_execute_result(self):
        """Test ExecuteResult."""
        result = ExecuteResult(output="test output", exit_code=0, truncated=False)
        assert result.output == "test output"
        assert result.exit_code == 0
        assert result.truncated is False
