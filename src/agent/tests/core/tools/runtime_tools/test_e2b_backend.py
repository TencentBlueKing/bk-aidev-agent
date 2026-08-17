# -*- coding: utf-8 -*-
"""Test module for E2BSandboxBackend.

本测试通过 mock E2B SDK 来验证：
- 初始化与环境变量读取
- 惰性创建与 kill 生命周期
- 文件与命令相关方法的签名与返回类型

注意：该测试不依赖真实的 E2B 网络环境。
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from datetime import datetime

import pytest
from aidev_agent.core.tools.runtime_tools.e2b_backend import E2BSandboxBackend
from aidev_agent.core.tools.runtime_tools.types import EditResult, ExecuteResult, WriteResult


@dataclass
class DummyCmdResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = 0


class DummyCommands:
    def __init__(self, handler):
        self._handler = handler

    def run(self, command: str, timeout: int | None = None):
        return self._handler(command, timeout)


class DummyEntryInfo:
    """模拟 E2B SDK 的 EntryInfo。"""

    def __init__(self, name: str, path: str, entry_type, size: int = 0):
        self.name = name
        self.path = path
        self.type = entry_type
        self.size = size
        self.mode = 0o644
        self.permissions = "rw-r--r--"
        self.owner = "user"
        self.group = "user"
        self.modified_time = datetime.now()
        self.symlink_target = None


class DummyFiles:
    """模拟 E2B SDK 的 sandbox.files 接口。"""

    def __init__(self):
        self._files: dict[str, str | bytes] = {}
        self._dirs: set[str] = set()

    def write(self, path: str, data):
        self._files[path] = data

    def read(self, path: str, format: str = "text"):
        if path not in self._files:
            raise FileNotFoundError(path)
        content = self._files[path]
        if format == "bytes":
            if isinstance(content, str):
                return bytearray(content.encode("utf-8"))
            return bytearray(content)
        if isinstance(content, bytes):
            return content.decode("utf-8")
        return content

    def exists(self, path: str) -> bool:
        return path in self._files or path in self._dirs

    def list(self, path: str, depth: int = 1):
        return self._list_entries


class DummySandbox:
    create_calls: list[dict] = []
    handler = None
    _dummy_files = None

    def __init__(self):
        assert DummySandbox.handler is not None
        assert DummySandbox._dummy_files is not None
        self.commands = DummyCommands(DummySandbox.handler)
        self.files = DummySandbox._dummy_files
        self.killed = False

    @classmethod
    def create(cls, **kwargs):
        cls.create_calls.append(kwargs)
        return cls()

    def kill(self):
        self.killed = True


@pytest.fixture(autouse=True)
def _patch_e2b_sdk(monkeypatch):
    """注入假 SDK：sys.modules 兜底 + 替换 e2b_backend 模块命名空间的顶层绑定。"""

    DummySandbox.create_calls = []
    DummySandbox.handler = lambda _cmd, _timeout=None: DummyCmdResult(stdout="", stderr="", exit_code=0)
    DummySandbox._dummy_files = DummyFiles()

    # 构造假的 e2b_code_interpreter 模块
    fake_e2b_ci = types.ModuleType("e2b_code_interpreter")
    fake_e2b_ci.Sandbox = DummySandbox
    monkeypatch.setitem(sys.modules, "e2b_code_interpreter", fake_e2b_ci)
    # e2b_backend 的 Sandbox 为顶层导入（import 绑定在模块命名空间），
    # 需直接替换该绑定才能让 _ensure_sandbox 拿到 Dummy
    monkeypatch.setattr(
        "aidev_agent.core.tools.runtime_tools.e2b_backend.Sandbox",
        DummySandbox,
    )


class TestE2BSandboxBackendInitialization:
    def test_init_default(self):
        backend = E2BSandboxBackend()
        assert backend._template == "sdt-hcomwqox"
        assert backend._timeout == 600

    def test_init_env_vars(self, monkeypatch):
        monkeypatch.setenv("E2B_API_KEY", "k")
        monkeypatch.setenv("E2B_DOMAIN", "d")
        backend = E2BSandboxBackend()
        assert backend._api_key == "k"
        assert backend._domain == "d"


class TestE2BSandboxBackendLifecycle:
    def test_lazy_create_and_reuse(self):
        backend = E2BSandboxBackend()
        assert backend._sandbox is None

        backend.ls_info("/workspace")
        assert backend._sandbox is not None
        assert len(DummySandbox.create_calls) == 1

        backend.ls_info("/workspace")
        assert len(DummySandbox.create_calls) == 1

    def test_kill(self):
        backend = E2BSandboxBackend()
        backend.ls_info("/workspace")
        sb = backend._sandbox
        assert sb is not None

        backend.kill()
        assert backend._sandbox is None
        assert sb.killed is True


class TestE2BSandboxBackendLsInfo:
    def test_ls_info_parsing(self):
        from e2b.sandbox.filesystem.filesystem import FileType

        dummy_files = DummyFiles()
        dummy_files._list_entries = [
            DummyEntryInfo(name="file1.txt", path="/workspace/file1.txt", entry_type=FileType.FILE),
            DummyEntryInfo(name="subdir", path="/workspace/subdir", entry_type=FileType.DIR),
        ]
        DummySandbox._dummy_files = dummy_files

        backend = E2BSandboxBackend()
        infos = backend.ls_info("/workspace")
        assert infos == [
            {"path": "/workspace/file1.txt", "is_dir": False},
            {"path": "/workspace/subdir/", "is_dir": True},
        ]


class TestE2BSandboxBackendRead:
    def test_read_success(self):
        dummy_files = DummyFiles()
        dummy_files._files["/workspace/test.txt"] = "line1\nline2\nline3\n"
        DummySandbox._dummy_files = dummy_files

        backend = E2BSandboxBackend()
        out = backend.read("/workspace/test.txt", offset=0, limit=2)
        assert "     1\tline1" in out
        assert "     2\tline2" in out

    def test_read_empty_file(self):
        dummy_files = DummyFiles()
        dummy_files._files["/workspace/empty.txt"] = ""
        DummySandbox._dummy_files = dummy_files

        backend = E2BSandboxBackend()
        out = backend.read("/workspace/empty.txt")
        assert "文件存在但内容为空" in out

    def test_read_offset_exceeds(self):
        dummy_files = DummyFiles()
        dummy_files._files["/workspace/test.txt"] = "line1\nline2\n"
        DummySandbox._dummy_files = dummy_files

        backend = E2BSandboxBackend()
        out = backend.read("/workspace/test.txt", offset=3, limit=10)
        assert "exceeds file length" in out

    def test_read_file_not_found(self):
        backend = E2BSandboxBackend()
        out = backend.read("/workspace/nonexistent.txt")
        assert "not found" in out


class TestE2BSandboxBackendWriteEdit:
    def test_write_success(self):
        dummy_files = DummyFiles()
        DummySandbox._dummy_files = dummy_files

        backend = E2BSandboxBackend()
        res = backend.write("/workspace/new.txt", "hello")
        assert isinstance(res, WriteResult)
        assert res.error is None
        assert res.path == "/workspace/new.txt"
        # 验证内容已写入
        assert dummy_files._files["/workspace/new.txt"] == "hello"

    def test_write_existing_fails(self):
        dummy_files = DummyFiles()
        dummy_files._files["/workspace/existing.txt"] = "old content"
        DummySandbox._dummy_files = dummy_files

        backend = E2BSandboxBackend()
        res = backend.write("/workspace/existing.txt", "hello")
        assert isinstance(res, WriteResult)
        assert res.error is not None
        assert "already exists" in res.error

    def test_edit_success(self):
        dummy_files = DummyFiles()
        dummy_files._files["/workspace/test.txt"] = "hello world\n"
        DummySandbox._dummy_files = dummy_files

        backend = E2BSandboxBackend()
        res = backend.edit("/workspace/test.txt", "world", "universe")
        assert isinstance(res, EditResult)
        assert res.error is None
        assert res.occurrences == 1
        # 验证内容已更新
        assert dummy_files._files["/workspace/test.txt"] == "hello universe\n"

    def test_edit_file_not_found(self):
        backend = E2BSandboxBackend()
        res = backend.edit("/workspace/nonexistent.txt", "old", "new")
        assert isinstance(res, EditResult)
        assert res.error is not None
        assert "not found" in res.error


class TestE2BSandboxBackendGrepGlobUploadDownloadExecute:
    def test_grep_invalid_regex(self):
        backend = E2BSandboxBackend()
        out = backend.grep_raw("[invalid(regex")
        assert isinstance(out, str)
        assert "Invalid regex" in out

    def test_grep_parsing(self):
        def handler(cmd: str, _timeout=None):
            if cmd.startswith("grep "):
                return DummyCmdResult(stdout="/workspace/a.txt:1:hello\n", exit_code=0)
            return DummyCmdResult(exit_code=0)

        DummySandbox.handler = handler

        backend = E2BSandboxBackend()
        out = backend.grep_raw("hello", path="/workspace")
        assert isinstance(out, list)
        assert out[0]["path"] == "/workspace/a.txt"
        assert out[0]["line"] == 1

    def test_glob_info(self):
        def handler(cmd: str, _timeout=None):
            if cmd.startswith("find "):
                return DummyCmdResult(stdout="/workspace/a.txt\n/workspace/b.txt\n", exit_code=0)
            return DummyCmdResult(exit_code=0)

        DummySandbox.handler = handler

        backend = E2BSandboxBackend()
        infos = backend.glob_info("*.txt", path="/workspace")
        assert [i["path"] for i in infos] == ["/workspace/a.txt", "/workspace/b.txt"]

    def test_upload_download(self):
        dummy_files = DummyFiles()
        DummySandbox._dummy_files = dummy_files

        backend = E2BSandboxBackend()
        up = backend.upload_files([("/workspace/u.txt", b"content")])
        assert up[0]["error"] is None

        down = backend.download_files(["/workspace/u.txt", "/workspace/missing.txt"])
        assert down[0]["content"] == b"content"
        assert down[1]["error"] == "file_not_found"

    def test_execute(self):
        def handler(cmd: str, _timeout=None):
            if cmd == "echo hello":
                return DummyCmdResult(stdout="hello\n", stderr="", exit_code=0)
            return DummyCmdResult(exit_code=0)

        DummySandbox.handler = handler

        backend = E2BSandboxBackend()
        res = backend.execute("echo hello")
        assert isinstance(res, ExecuteResult)
        assert "hello" in res.output
        assert res.exit_code == 0

    @pytest.mark.asyncio
    async def test_aexecute(self):
        def handler(cmd: str, _timeout=None):
            if cmd == "echo hello":
                return DummyCmdResult(stdout="hello\n", stderr="", exit_code=0)
            return DummyCmdResult(exit_code=0)

        DummySandbox.handler = handler

        backend = E2BSandboxBackend()
        res = await backend.aexecute("echo hello")
        assert isinstance(res, ExecuteResult)
        assert res.exit_code == 0


class TestConfigStatePassThrough:
    """测试 E2BSandboxBackend 方法签名接受 config/state 参数。"""

    def test_ls_info_accepts_config_state_kwargs(self):
        """ls_info 应接受 keyword-only config/state 参数（签名验证）。"""
        import inspect

        sig = inspect.signature(E2BSandboxBackend.ls_info)
        params = sig.parameters
        assert "config" in params, "ls_info 缺少 config 参数"
        assert "state" in params, "ls_info 缺少 state 参数"
        assert params["config"].kind == inspect.Parameter.KEYWORD_ONLY, "config 应为 keyword-only"
        assert params["state"].kind == inspect.Parameter.KEYWORD_ONLY, "state 应为 keyword-only"
