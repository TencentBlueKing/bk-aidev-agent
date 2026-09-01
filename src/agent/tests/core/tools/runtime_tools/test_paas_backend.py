# -*- coding: utf-8 -*-
"""Test module for PaasSandboxBackend.

通过 monkeypatch mock requests 来验证：
- 惰性创建与 kill 生命周期
- 文件与命令相关方法的签名与返回类型
- 错误处理

注意：该测试不依赖真实的 PaaS 网络环境。
"""

from __future__ import annotations

import inspect
import re
import threading
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.tools.runtime_tools.paas_backend import ExecResult, PaasSandboxBackend
from aidev_agent.core.tools.runtime_tools.types import EditResult, ExecuteResult, WriteResult
from aidev_agent.utils.tracing import set_agent_tracer
from requests.exceptions import HTTPError

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

_PAAS_BACKEND_MOD = "aidev_agent.core.tools.runtime_tools.paas_backend"


def _make_response(*, status_code: int = 200, json_data=None, content: bytes = b""):
    """创建一个可用于 mock 的 requests.Response 替身。"""

    class _Resp:
        def __init__(self):
            self.status_code = status_code
            self.content = content
            self._json_data = json_data

        def json(self):
            return self._json_data

    return _Resp()


def _make_http_response(*, status_code: int = 200, json_data=None, content: bytes = b""):
    """创建一个可用于 mock 的 HTTP Response 替身（用于 client 层 API 测试）。"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    if status_code >= 400:
        resp.raise_for_status.side_effect = HTTPError(response=resp)
    return resp


def _make_backend(**kwargs) -> PaasSandboxBackend:
    """创建一个带默认参数的 PaasSandboxBackend 实例，用于测试 HTTP 方法。"""
    defaults = dict(
        app_code="test-app",
        bk_username="test-username",
        client=MagicMock(),
        snapshot="",
        snapshot_entrypoint=[],
        env_vars={},
    )
    defaults.update(kwargs)
    return PaasSandboxBackend(**defaults)


class MockOps:
    """记录沙箱操作调用，代替原来的 MockClient。

    通过 monkeypatch 将 PaasSandboxBackend 的底层 HTTP 方法替换为此对象的实现，
    从而在不发真实 HTTP 请求的情况下验证 Backend 的业务逻辑。

    注意：~ 路径展开由 Backend 的 _resolve_path 在公开方法入口统一处理，
    到达 upload_file/download_file 时路径已是绝对路径。
    """

    def __init__(self):
        self.sandbox_created = False
        self.sandbox_destroyed = False
        self.exec_handler = lambda sandbox_id, cmd, **kw: ExecResult(stdout="", stderr="", exit_code=0)
        self.uploaded_files: dict[str, bytes] = {}

    def create_sandbox(self, name=None, env_vars=None, snapshot=None, snapshot_entrypoint=None, **kwargs):
        self.sandbox_created = True
        return "mock-sandbox-id"

    def destroy_sandbox(self, sandbox_id):
        self.sandbox_destroyed = True

    def exec_command(self, sandbox_id, cmd, cwd=None, env=None, timeout=None):
        return self.exec_handler(sandbox_id, cmd, cwd=cwd, env=env, timeout=timeout)

    def upload_file(self, sandbox_id, path, content):
        self.uploaded_files[path] = content

    def download_file(self, sandbox_id, path):
        if path not in self.uploaded_files:
            raise FileNotFoundError(f"HTTP 404: file not found: {path}")
        return self.uploaded_files[path]


@pytest.fixture()
def mock_ops():
    return MockOps()


@pytest.fixture()
def backend(mock_ops, monkeypatch):
    """创建 PaasSandboxBackend 实例，并将其所有 HTTP 方法替换为 mock_ops 的实现。

    同时绕过 _paas_error_enhance 装饰器，使方法直接抛出标准异常
    (FileNotFoundError / FileExistsError / ValueError / IndexError / OSError / re.error)，
    便于在测试中精确断言异常类型。
    """
    b = PaasSandboxBackend(
        app_code="test-app",
        bk_username="test-username",
        client=MagicMock(),
        snapshot="test-snapshot",
        snapshot_entrypoint=["python", "-m", "server"],
        env_vars={},
    )
    # 将实例方法替换为 mock_ops 的方法，保持 self 绑定到 b
    monkeypatch.setattr(b, "create_sandbox", mock_ops.create_sandbox)
    monkeypatch.setattr(b, "destroy_sandbox", mock_ops.destroy_sandbox)
    monkeypatch.setattr(b, "exec_command", mock_ops.exec_command)
    monkeypatch.setattr(b, "upload_file", mock_ops.upload_file)
    monkeypatch.setattr(b, "download_file", mock_ops.download_file)

    # 绕过 _paas_error_enhance 装饰器，使异常以原始类型抛出
    _unwrapped_methods = ["ls_info", "read", "write", "edit", "grep_raw"]
    for _name in _unwrapped_methods:
        _unwrap = getattr(type(b), _name).__wrapped__

        def _make_caller(name=_name, unwrapped=_unwrap):
            def _call(*args, **kwargs):
                return unwrapped(b, *args, **kwargs)

            return _call

        monkeypatch.setattr(b, _name, _make_caller())

    return b


class TestPaasSandboxBackendLifecycle:
    def test_lazy_create(self, backend, mock_ops):
        """首次调用操作方法时才创建沙箱。"""
        assert backend._sandbox_id is None
        assert not mock_ops.sandbox_created

        backend.ls_info("/app")
        assert backend._sandbox_id == "mock-sandbox-id"
        assert mock_ops.sandbox_created

    def test_reuse_sandbox(self, backend, mock_ops):
        """后续调用复用沙箱 ID。"""
        backend.ls_info("/app")
        backend.ls_info("/app")
        # create_sandbox 只被调用一次（通过检查 sandbox_created 标记）
        assert backend._sandbox_id == "mock-sandbox-id"

    def test_kill(self, backend, mock_ops):
        """kill 销毁沙箱并重置 ID。"""
        backend.ls_info("/app")
        assert backend._sandbox_id is not None

        backend.kill()
        assert backend._sandbox_id is None
        assert mock_ops.sandbox_destroyed

    def test_kill_when_not_created(self, backend, mock_ops):
        """未创建时 kill 不会调用 destroy。"""
        backend.kill()
        assert not mock_ops.sandbox_destroyed

    def test_recreate_after_kill(self, backend, mock_ops):
        """kill 后再次调用操作方法会重新创建。"""
        backend.ls_info("/app")
        backend.kill()

        mock_ops.sandbox_created = False
        backend.ls_info("/app")
        assert mock_ops.sandbox_created
        assert backend._sandbox_id == "mock-sandbox-id"


class TestPaasSandboxBackendLsInfo:
    def test_ls_info_parsing(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            # ls_info 使用 ["bash", "-c", cmd] 形式执行
            actual_cmd = cmd[-1] if isinstance(cmd, list) else cmd
            if actual_cmd.startswith("ls "):
                return ExecResult(stdout="file1.txt\nsubdir/\n", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        infos = backend.ls_info("/app")
        assert infos == [
            {"path": "/app/file1.txt", "is_dir": False},
            {"path": "/app/subdir/", "is_dir": True},
        ]

    def test_ls_info_failure(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            return ExecResult(stdout="", stderr="No such directory", exit_code=2)

        mock_ops.exec_handler = handler
        with pytest.raises(OSError, match="Cannot list directory"):
            backend.ls_info("/nonexistent")


class TestPaasSandboxBackendRead:
    def test_read_success(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            if cmd.startswith("test -f "):
                return ExecResult(stdout="", stderr="", exit_code=0)
            if "END{print NR}" in cmd:
                return ExecResult(stdout="3\n", stderr="", exit_code=0)
            if cmd.startswith("awk "):
                return ExecResult(stdout="     1\tline1\n     2\tline2\n", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        out = backend.read("/app/test.txt", offset=0, limit=2)
        assert "     1\tline1" in out
        assert "     2\tline2" in out

    def test_read_file_not_found(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            if cmd.startswith("test -f "):
                return ExecResult(stdout="", stderr="", exit_code=1)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        with pytest.raises(FileNotFoundError, match="not found"):
            backend.read("/app/missing.txt")

    def test_read_empty_file(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            if cmd.startswith("test -f "):
                return ExecResult(stdout="", stderr="", exit_code=0)
            if "END{print NR}" in cmd:
                return ExecResult(stdout="0\n", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        out = backend.read("/app/empty.txt")
        assert "文件存在但内容为空" in out

    def test_read_offset_exceeds(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            if cmd.startswith("test -f "):
                return ExecResult(stdout="", stderr="", exit_code=0)
            if "END{print NR}" in cmd:
                return ExecResult(stdout="2\n", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        with pytest.raises(IndexError, match="exceeds file length"):
            backend.read("/app/test.txt", offset=5)


class TestPaasSandboxBackendWrite:
    def test_write_success(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            if cmd.startswith("test -e "):
                return ExecResult(stdout="", stderr="", exit_code=1)  # 文件不存在
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        res = backend.write("/app/new.txt", "hello")
        assert isinstance(res, WriteResult)
        assert res.error is None
        assert res.path == "/app/new.txt"
        assert "/app/new.txt" in mock_ops.uploaded_files
        assert mock_ops.uploaded_files["/app/new.txt"] == b"hello"

    def test_write_existing_fails(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            if cmd.startswith("test -e "):
                return ExecResult(stdout="", stderr="", exit_code=0)  # 文件存在
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        with pytest.raises(FileExistsError, match="already exists"):
            backend.write("/app/existing.txt", "hello")


class TestPaasSandboxBackendEdit:
    def test_edit_success(self, backend, mock_ops):
        # 预先上传文件
        mock_ops.uploaded_files["/app/test.txt"] = b"hello world\n"

        def handler(sandbox_id, cmd, **kw):
            if cmd.startswith("cat "):
                return ExecResult(stdout="hello world\n", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        res = backend.edit("/app/test.txt", "world", "universe")
        assert isinstance(res, EditResult)
        assert res.error is None
        assert res.occurrences == 1
        # 验证文件内容已更新
        assert mock_ops.uploaded_files["/app/test.txt"] == b"hello universe\n"

    def test_edit_file_not_found(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            if cmd.startswith("cat "):
                return ExecResult(stdout="", stderr="No such file", exit_code=1)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        with pytest.raises(FileNotFoundError, match="not found"):
            backend.edit("/app/missing.txt", "old", "new")

    def test_edit_string_not_found(self, backend, mock_ops):
        mock_ops.uploaded_files["/app/test.txt"] = b"hello world\n"

        def handler(sandbox_id, cmd, **kw):
            if cmd.startswith("cat "):
                return ExecResult(stdout="hello world\n", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        with pytest.raises(ValueError, match="未找到匹配"):
            backend.edit("/app/test.txt", "nonexistent", "replacement")


class TestPaasSandboxBackendGrepGlob:
    def test_grep_parsing(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            if cmd.startswith("grep "):
                return ExecResult(stdout="/app/a.txt:1:hello world\n/app/b.txt:5:hello again\n", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        out = backend.grep_raw("hello", path="/app")
        assert isinstance(out, list)
        assert len(out) == 2
        assert out[0]["path"] == "/app/a.txt"
        assert out[0]["line"] == 1
        assert out[0]["text"] == "hello world"

    def test_grep_invalid_regex(self, backend):
        with pytest.raises(re.error):
            backend.grep_raw("[invalid(regex")

    def test_grep_with_glob_filter(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            assert "--include=" in cmd
            return ExecResult(stdout="", stderr="", exit_code=1)

        mock_ops.exec_handler = handler
        backend.grep_raw("pattern", path="/app", glob="*.py")

    def test_glob_info(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            if cmd.startswith("find "):
                return ExecResult(stdout="/app/a.txt\n/app/b.txt\n", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        infos = backend.glob_info("*.txt", path="/app")
        assert len(infos) == 2
        assert [i["path"] for i in infos] == ["/app/a.txt", "/app/b.txt"]

    def test_glob_info_failure(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            return ExecResult(stdout="", stderr="error", exit_code=2)

        mock_ops.exec_handler = handler
        assert backend.glob_info("*.txt", path="/nonexistent") == []


class TestPaasSandboxBackendUploadDownload:
    def test_upload_files(self, backend, mock_ops):
        responses = backend.upload_files(
            [
                ("/app/a.txt", b"content-a"),
                ("/app/b.txt", b"content-b"),
            ]
        )
        assert len(responses) == 2
        assert responses[0]["error"] is None
        assert responses[1]["error"] is None
        assert mock_ops.uploaded_files["/app/a.txt"] == b"content-a"

    def test_download_files(self, backend, mock_ops):
        mock_ops.uploaded_files["/app/a.txt"] = b"content-a"

        responses = backend.download_files(["/app/a.txt", "/app/missing.txt"])
        assert len(responses) == 2
        assert responses[0]["content"] == b"content-a"
        assert responses[0]["error"] is None
        assert responses[1]["content"] is None
        assert responses[1]["error"] is not None


class TestPaasSandboxBackendExecute:
    def test_execute_success(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            return ExecResult(stdout="hello\n", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        res = backend.execute("echo hello")
        assert isinstance(res, ExecuteResult)
        assert "hello" in res.output
        assert res.exit_code == 0
        assert not res.truncated

    def test_execute_with_stderr(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            return ExecResult(stdout="out", stderr="err", exit_code=1)

        mock_ops.exec_handler = handler

        res = backend.execute("bad command")
        assert "out" in res.output
        assert "err" in res.output
        assert res.exit_code == 1

    def test_execute_truncation(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            return ExecResult(stdout="x" * 200, stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        res = backend.execute("big output", max_output_size=100)
        assert len(res.output) == 100
        assert res.truncated

    @pytest.mark.asyncio
    async def test_aexecute(self, backend, mock_ops):
        def handler(sandbox_id, cmd, **kw):
            return ExecResult(stdout="async hello\n", stderr="", exit_code=0)

        mock_ops.exec_handler = handler

        res = await backend.aexecute("echo hello")
        assert isinstance(res, ExecuteResult)
        assert "async hello" in res.output
        assert res.exit_code == 0


def _is_echo_home(cmd) -> bool:
    """判断 cmd 是否为 echo $HOME 命令（兼容字符串和列表格式）。"""
    if isinstance(cmd, list):
        return len(cmd) == 3 and cmd[2] == "echo $HOME"
    return cmd == "echo $HOME"


class TestResolvePath:
    """验证 _resolve_path 将 ~ 展开为绝对路径，供 HTTP API 使用。"""

    def test_absolute_path_unchanged(self, backend, mock_ops):
        """绝对路径原样返回，不触发 shell 调用。"""
        assert backend._resolve_path("/app/test.txt") == "/app/test.txt"

    def test_tilde_only(self, backend, mock_ops):
        """单独 ~ 展开为 $HOME。"""

        def handler(sandbox_id, cmd, **kw):
            if _is_echo_home(cmd):
                return ExecResult(stdout="/root\n", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler
        assert backend._resolve_path("~") == "/root"

    def test_tilde_with_subpath(self, backend, mock_ops):
        """~/sub/path 展开为 /root/sub/path。"""

        def handler(sandbox_id, cmd, **kw):
            if _is_echo_home(cmd):
                return ExecResult(stdout="/root\n", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler
        assert backend._resolve_path("~/foo/bar.txt") == "/root/foo/bar.txt"

    def test_tilde_slash_only(self, backend, mock_ops):
        """~/ 展开为 /root/。"""

        def handler(sandbox_id, cmd, **kw):
            if _is_echo_home(cmd):
                return ExecResult(stdout="/root\n", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler
        assert backend._resolve_path("~/") == "/root/"

    def test_home_dir_cached(self, backend, mock_ops):
        """第二次调用不再执行 echo $HOME，直接复用缓存。"""
        call_count = 0

        def handler(sandbox_id, cmd, **kw):
            nonlocal call_count
            if _is_echo_home(cmd):
                call_count += 1
                return ExecResult(stdout="/home/user\n", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        mock_ops.exec_handler = handler
        backend._resolve_path("~/a.txt")
        backend._resolve_path("~/b.txt")
        assert call_count == 1
        assert backend._resolve_path("~/c.txt") == "/home/user/c.txt"


class TestTildePathIntegration:
    """验证 ~ 路径在各方法中的端到端处理。"""

    def _make_handler(self, mock_ops):
        """返回一个 exec_handler，模拟 shell 命令行为。

        由于 _resolve_path 在入口层已将 ~ 展开为 /root，
        shell 命令中的路径都是绝对路径（经 shlex.quote 转义），
        不再出现 $HOME。
        """

        def _extract_path(cmd: str) -> str:
            """从 shell 命令末尾提取被 shlex.quote 转义的路径。"""
            # shlex.quote 产生 '/root/xxx' 形式
            path_part = cmd.rsplit(" ", 1)[-1].strip("'\"")
            return path_part

        def handler(sandbox_id, cmd, **kw):
            # _resolve_path 探测 HOME（列表格式 ["/bin/sh", "-c", "echo $HOME"]）
            if _is_echo_home(cmd):
                return ExecResult(stdout="/root\n", stderr="", exit_code=0)
            # ls_info 传 ["bash", "-c", cmd_str]，其余方法传字符串
            actual_cmd = cmd[-1] if isinstance(cmd, list) and len(cmd) >= 1 else cmd
            # test -e / test -f
            if actual_cmd.startswith(("test -e ", "test -f ")):
                path = _extract_path(actual_cmd)
                if path in mock_ops.uploaded_files:
                    return ExecResult(stdout="", stderr="", exit_code=0)
                return ExecResult(stdout="", stderr="", exit_code=1)
            # mkdir
            if actual_cmd.startswith("mkdir "):
                return ExecResult(stdout="", stderr="", exit_code=0)
            # cat (edit 读取)
            if actual_cmd.startswith("cat "):
                path = _extract_path(actual_cmd)
                if path in mock_ops.uploaded_files:
                    return ExecResult(
                        stdout=mock_ops.uploaded_files[path].decode("utf-8", errors="replace"),
                        stderr="",
                        exit_code=0,
                    )
                return ExecResult(stdout="", stderr="No such file", exit_code=1)
            # awk 行数统计
            if "END{print NR}" in actual_cmd:
                path = _extract_path(actual_cmd)
                if path in mock_ops.uploaded_files:
                    content = mock_ops.uploaded_files[path].decode("utf-8", errors="replace")
                    lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
                    return ExecResult(stdout=f"{lines}\n", stderr="", exit_code=0)
                return ExecResult(stdout="0\n", stderr="", exit_code=0)
            # awk 带行号输出
            if actual_cmd.startswith("awk "):
                path = _extract_path(actual_cmd)
                if path in mock_ops.uploaded_files:
                    content = mock_ops.uploaded_files[path].decode("utf-8", errors="replace")
                    lines = content.split("\n")
                    if lines and lines[-1] == "":
                        lines = lines[:-1]
                    out = "\n".join(f"{i + 1:>6}\t{line}" for i, line in enumerate(lines))
                    return ExecResult(stdout=out + "\n", stderr="", exit_code=0)
                return ExecResult(stdout="", stderr="", exit_code=0)
            # rm
            if actual_cmd.startswith("rm "):
                path = _extract_path(actual_cmd)
                mock_ops.uploaded_files.pop(path, None)
                return ExecResult(stdout="", stderr="", exit_code=0)
            return ExecResult(stdout="", stderr="", exit_code=0)

        return handler

    def test_write_tilde_then_read_tilde(self, backend, mock_ops):
        """write('~/f.txt') 后 read('~/f.txt') 能正确读取。"""
        mock_ops.exec_handler = self._make_handler(mock_ops)

        w = backend.write("~/test.txt", "hello tilde\n")
        assert w.error is None
        # upload_file 应通过 _resolve_path 将 ~/test.txt 转为 /root/test.txt
        assert "/root/test.txt" in mock_ops.uploaded_files

        r = backend.read("~/test.txt", offset=0, limit=10)
        assert "hello tilde" in r

    def test_write_tilde_duplicate_detected(self, backend, mock_ops):
        """write('~/f.txt') 两次时，第二次应抛出 FileExistsError。"""
        mock_ops.exec_handler = self._make_handler(mock_ops)

        w1 = backend.write("~/dup.txt", "first")
        assert w1.error is None

        with pytest.raises(FileExistsError, match="already exists"):
            backend.write("~/dup.txt", "second")

    def test_edit_tilde_path(self, backend, mock_ops):
        """edit('~/f.txt') 能正确读取、修改并写回文件。"""
        mock_ops.exec_handler = self._make_handler(mock_ops)
        # 预写入
        backend.write("~/edit_me.txt", "old content\n")

        e = backend.edit("~/edit_me.txt", "old", "new")
        assert e.error is None
        assert e.occurrences == 1
        assert mock_ops.uploaded_files["/root/edit_me.txt"] == b"new content\n"

    def test_upload_tilde_download_tilde(self, backend, mock_ops):
        """upload_files('~/f.bin') 后 download_files('~/f.bin') 内容一致。"""
        mock_ops.exec_handler = self._make_handler(mock_ops)

        payload = b"\x00\x01binary"
        up = backend.upload_files([("~/bin.dat", payload)])
        assert up[0]["error"] is None
        assert "/root/bin.dat" in mock_ops.uploaded_files

        down = backend.download_files(["~/bin.dat"])
        assert down[0]["error"] is None
        assert down[0]["content"] == payload

    def test_write_empty_content(self, backend, mock_ops):
        """write('', '') 应抛出 ValueError。"""
        mock_ops.exec_handler = self._make_handler(mock_ops)

        with pytest.raises(ValueError, match="empty"):
            backend.write("/app/empty.txt", "")


class TestPaasSandboxBackendInit:
    def test_init_basic_attributes(self):
        """验证构造函数正确赋值所有属性。"""
        backend = PaasSandboxBackend(
            app_code="explicit-app",
            bk_username="explicit-username",
            client=MagicMock(),
            snapshot="test-snapshot",
            snapshot_entrypoint=["python", "-m", "server"],
            env_vars={},
        )
        assert backend._app_code == "explicit-app"
        assert backend._sandbox_id is None

    def test_init_with_params(self):
        """验证 snapshot、snapshot_entrypoint、env_vars 等参数正确赋值。"""
        backend = PaasSandboxBackend(
            app_code="param-app",
            bk_username="param-username",
            client=MagicMock(),
            snapshot="param-snapshot",
            snapshot_entrypoint=["python", "-m", "server"],
            env_vars={"KEY": "VALUE"},
        )
        assert backend._snapshot == "param-snapshot"
        assert backend._snapshot_entrypoint == ["python", "-m", "server"]
        assert backend._env_vars == {"KEY": "VALUE"}

    def test_init_with_workspace_ttl(self):
        """验证 __init__ 新增 workspace/ttl_seconds 参数正确赋值。"""
        backend = PaasSandboxBackend(
            app_code="app",
            bk_username="u",
            client=MagicMock(),
            snapshot="snap",
            snapshot_entrypoint=[],
            env_vars={},
            workspace="/app",
            ttl_seconds=3600,
        )
        assert backend._workspace == "/app"
        assert backend._ttl_seconds == 3600

    def test_init_workspace_ttl_defaults_to_none(self):
        """验证 workspace/ttl_seconds 默认值为 None。"""
        backend = PaasSandboxBackend(
            app_code="app",
            bk_username="u",
            client=MagicMock(),
            snapshot="snap",
            snapshot_entrypoint=[],
            env_vars={},
        )
        assert backend._workspace is None
        assert backend._ttl_seconds is None

    def test_init_api_host_trailing_slash_stripped(self):
        """验证默认参数可以正常构造实例。"""
        backend = PaasSandboxBackend(
            app_code="app",
            bk_username="username",
            client=MagicMock(),
            snapshot="snap",
            snapshot_entrypoint=[],
            env_vars={},
        )
        assert backend._app_code == "app"


class TestPaasSandboxBackendAuth:
    """测试配置项显式注入。"""

    def test_explicit_params(self):
        """所有配置项均通过构造函数显式注入，不依赖任何环境变量。"""
        backend = _make_backend(
            app_code="explicit-app",
        )
        assert backend._app_code == "explicit-app"


class TestPaasSandboxBackendErrors:
    """测试错误处理。"""

    def test_missing_app_code(self):
        backend = _make_backend(app_code="")
        with pytest.raises(ValueError, match="app_code"):
            backend.create_sandbox()


class TestPaasSandboxBackendHTTPMethods:
    """测试各 HTTP API 方法（通过 mock client）。"""

    def test_exec_command_records_sandbox_client_span(self, http_backend):
        TracerProvider = pytest.importorskip("opentelemetry.sdk.trace").TracerProvider
        SimpleSpanProcessor = pytest.importorskip("opentelemetry.sdk.trace.export").SimpleSpanProcessor
        InMemorySpanExporter = pytest.importorskip(
            "opentelemetry.sdk.trace.export.in_memory_span_exporter"
        ).InMemorySpanExporter
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        set_agent_tracer(provider.get_tracer(__name__))
        http_backend.client.exec_command.request.return_value = _make_http_response(
            json_data={"stdout": "ok", "stderr": "", "exit_code": 0}
        )

        try:
            http_backend.exec_command("sb-123", "echo hello")
        finally:
            set_agent_tracer(None)

        span = exporter.get_finished_spans()[0]
        assert span.name == "sandbox.execute"
        assert span.kind.name == "CLIENT"
        assert span.attributes["sandbox.operation.name"] == "execute"
        assert "echo hello" not in str(span.attributes)

    def test_exec_command_propagates_current_trace_context(self, http_backend, monkeypatch):
        traceparent = "00-992eea94222b572e883ab78b23e73d64-99e019654b49749a-01"
        monkeypatch.setattr(f"{_PAAS_BACKEND_MOD}.trace_headers", lambda: {"traceparent": traceparent})
        http_backend.client.exec_command.request.return_value = _make_http_response(
            json_data={"stdout": "ok", "stderr": "", "exit_code": 0}
        )

        http_backend.exec_command("sb-123", "echo hello")

        assert http_backend.client.exec_command.request.call_args.kwargs["headers"] == {"traceparent": traceparent}

    @pytest.fixture()
    def http_backend(self):
        b = _make_backend()
        b.client = MagicMock()
        return b

    def test_create_sandbox(self, http_backend):
        http_backend.client.create_sandbox.request.return_value = _make_http_response(json_data={"uuid": "sb-123"})

        sandbox_id = http_backend.create_sandbox(name="test")
        assert sandbox_id == "sb-123"

        http_backend.client.create_sandbox.request.assert_called_once_with(
            json={"name": "test"},
            path_params={"app_code": "test-app"},
        )

    def test_destroy_sandbox(self, http_backend):
        http_backend.client.delete_sandbox.request.return_value = _make_http_response()

        http_backend.destroy_sandbox("sb-123")

        http_backend.client.delete_sandbox.request.assert_called_once_with(
            path_params={"sandbox_id": "sb-123"}, timeout=10
        )

    def test_exec_command(self, http_backend):
        http_backend.client.exec_command.request.return_value = _make_http_response(
            json_data={"stdout": "hello\n", "stderr": "", "exit_code": 0}
        )

        result = http_backend.exec_command("sb-123", "echo hello")
        assert result.stdout == "hello\n"
        assert result.stderr == ""
        assert result.exit_code == 0

        http_backend.client.exec_command.request.assert_called_once_with(
            json={"cmd": "echo hello"},
            path_params={"sandbox_id": "sb-123"},
        )

    def test_upload_file(self, http_backend):
        http_backend.client.upload_file.request.return_value = _make_http_response(
            json_data={"code": 0, "data": None, "message": "ok"}
        )

        http_backend.upload_file("sb-123", "/app/test.txt", b"hello content")

        http_backend.client.upload_file.request.assert_called_once_with(
            files={"file": ("test.txt", b"hello content"), "path": (None, "/app/test.txt")},
            path_params={"sandbox_id": "sb-123"},
        )

    def test_download_file(self, http_backend):
        content = b"file content here"
        http_backend.client.download_file.request.return_value = _make_http_response(content=content)

        result = http_backend.download_file("sb-123", "/app/test.txt")
        assert result == content

        http_backend.client.download_file.request.assert_called_once_with(
            params={"path": "/app/test.txt"},
            path_params={"sandbox_id": "sb-123"},
        )

    def test_create_sandbox_full_params(self, http_backend):
        """验证全部 7 参数正确传递到 API 请求。"""
        http_backend.client.create_sandbox.request.return_value = _make_http_response(json_data={"uuid": "sb-full"})

        sandbox_id = http_backend.create_sandbox(
            name="test",
            env_vars={"KEY": "VAL"},
            snapshot="snap",
            snapshot_entrypoint=["python"],
            workspace="/app",
            ttl_seconds=3600,
            volume_mounts=[{"volume_id": "vol-uuid", "mount_path": "/data"}],
        )
        assert sandbox_id == "sb-full"

        http_backend.client.create_sandbox.request.assert_called_once_with(
            json={
                "name": "test",
                "env_vars": {"KEY": "VAL"},
                "snapshot": "snap",
                "snapshot_entrypoint": ["python"],
                "workspace": "/app",
                "ttl_seconds": 3600,
                "volume_mounts": [{"volume_id": "vol-uuid", "mount_path": "/data"}],
            },
            path_params={"app_code": "test-app"},
        )

    def test_create_sandbox_workspace_fallback_to_init(self, http_backend):
        """验证 workspace 未传入方法时回退到 __init__ 实例默认值。"""
        backend = _make_backend(workspace="/default-workspace")
        backend.client = MagicMock()
        backend.client.create_sandbox.request.return_value = _make_http_response(json_data={"uuid": "sb-fallback"})

        sandbox_id = backend.create_sandbox(name="test")
        assert sandbox_id == "sb-fallback"

        call_kwargs = backend.client.create_sandbox.request.call_args
        assert call_kwargs.kwargs["json"]["workspace"] == "/default-workspace"

    def test_create_sandbox_ttl_fallback_to_init(self, http_backend):
        """验证 ttl_seconds 未传入方法时回退到 __init__ 实例默认值。"""
        backend = _make_backend(ttl_seconds=7200)
        backend.client = MagicMock()
        backend.client.create_sandbox.request.return_value = _make_http_response(json_data={"uuid": "sb-fallback"})

        sandbox_id = backend.create_sandbox(name="test")
        assert sandbox_id == "sb-fallback"

        call_kwargs = backend.client.create_sandbox.request.call_args
        assert call_kwargs.kwargs["json"]["ttl_seconds"] == 7200

    def test_create_sandbox_method_param_overrides_init(self, http_backend):
        """验证方法参数优先于 __init__ 实例默认值。"""
        backend = _make_backend(workspace="/init-workspace", ttl_seconds=3600)
        backend.client = MagicMock()
        backend.client.create_sandbox.request.return_value = _make_http_response(json_data={"uuid": "sb-override"})

        sandbox_id = backend.create_sandbox(name="test", workspace="/method-workspace", ttl_seconds=7200)
        assert sandbox_id == "sb-override"

        call_kwargs = backend.client.create_sandbox.request.call_args
        assert call_kwargs.kwargs["json"]["workspace"] == "/method-workspace"
        assert call_kwargs.kwargs["json"]["ttl_seconds"] == 7200

    def test_create_sandbox_volume_mounts(self, http_backend):
        """验证 volume_mounts 正确传递到 API 请求。"""
        http_backend.client.create_sandbox.request.return_value = _make_http_response(json_data={"uuid": "sb-vol"})

        volume_mounts = [{"volume_id": "vol-uuid-1", "mount_path": "/data/shared"}]
        sandbox_id = http_backend.create_sandbox(name="test", volume_mounts=volume_mounts)
        assert sandbox_id == "sb-vol"

        call_kwargs = http_backend.client.create_sandbox.request.call_args
        assert call_kwargs.kwargs["json"]["volume_mounts"] == volume_mounts


class TestEnsureSandboxConcurrency:
    """测试 _ensure_sandbox 的并发安全性。"""

    def test_concurrent_ensure_sandbox_creates_once(self, monkeypatch):
        """多线程并发调用 _ensure_sandbox 时，create_sandbox 只执行一次。"""
        backend = PaasSandboxBackend(
            app_code="test-app",
            bk_username="user",
            client=MagicMock(),
            snapshot="snap",
            snapshot_entrypoint=[],
            env_vars={},
        )
        mock_create = MagicMock(return_value="sandbox-123")
        monkeypatch.setattr(backend, "create_sandbox", mock_create)
        monkeypatch.setattr("aidev_agent.core.tools.runtime_tools.paas_backend.sleep", lambda _: None)

        results: list[str | None] = [None] * 10

        def worker(idx):
            results[idx] = backend._ensure_sandbox()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert mock_create.call_count == 1
        assert all(r == "sandbox-123" for r in results)

    def test_ensure_sandbox_passes_workspace_ttl(self, monkeypatch):
        """验证 _ensure_sandbox 将 workspace/ttl_seconds 传递给 create_sandbox。"""
        backend = PaasSandboxBackend(
            app_code="test-app",
            bk_username="u",
            client=MagicMock(),
            snapshot="snap",
            snapshot_entrypoint=[],
            env_vars={},
            workspace="/app",
            ttl_seconds=3600,
        )
        mock_create = MagicMock(return_value="sandbox-123")
        monkeypatch.setattr(backend, "create_sandbox", mock_create)
        monkeypatch.setattr(
            "aidev_agent.core.tools.runtime_tools.paas_backend.sleep",
            lambda _: None,
        )

        backend._ensure_sandbox()
        mock_create.assert_called_once_with(
            snapshot="snap",
            snapshot_entrypoint=[],
            env_vars={},
            workspace="/app",
            ttl_seconds=3600,
            volume_mounts=None,
        )


class TestConfigStatePassThrough:
    """测试 PaasSandboxBackend 方法签名接受 config/state 参数。"""

    def test_ls_info_accepts_config_state_kwargs(self):
        """ls_info 应接受 keyword-only config/state 参数（签名验证）。"""
        sig = inspect.signature(PaasSandboxBackend.ls_info)
        params = sig.parameters
        assert "config" in params, "ls_info 缺少 config 参数"
        assert "state" in params, "ls_info 缺少 state 参数"
        assert params["config"].kind == inspect.Parameter.KEYWORD_ONLY, "config 应为 keyword-only"
        assert params["state"].kind == inspect.Parameter.KEYWORD_ONLY, "state 应为 keyword-only"
