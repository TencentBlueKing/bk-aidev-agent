# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

from aidev_agent.core.tools.runtime_tools.bubblewrap_backend import BubblewrapFilesystemBackend, BwrapResult
from aidev_agent.core.tools.runtime_tools.types import ReadResult


def _bwrap_backend(tmp_path, *, bwrap, sandbox_policy=None):
    """构造已就绪的 backend，并把 bwrap mock 直接作为执行原语。"""
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path), sandbox_policy=sandbox_policy)
    if bwrap is not None:
        backend._read_text = bwrap.read_text
        backend._available = True
    return backend


def test_probe_runs_at_init(tmp_path):
    """独立后端在构造期即探测 bwrap，结果经 is_available() 暴露。"""
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path), bwrap_path="/nonexistent/bwrap-xyz")
    assert backend._available is False
    assert backend.is_available() is False


def test_unavailable_sandbox_returns_empty_ls(tmp_path):
    """bwrap 二进制缺失时 ls_info 经沙箱调用，探测失败即无条目（不绕回宿主机）。"""
    (tmp_path / "foo.txt").write_text("hello")
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path), bwrap_path="/nonexistent/bwrap-xyz")
    assert backend.is_available() is False
    # find 在不可用沙箱下必然失败 ⇒ 空列表；宿主机上的 foo.txt 不可见
    assert backend.ls_info("/") == []


def test_read_routes_to_bwrap(tmp_path):
    """read 走 bwrap 子进程，返回原始行数据。"""
    fake = MagicMock()
    fake.read_text.return_value = "line-one\nline-two\n"
    backend = _bwrap_backend(tmp_path, bwrap=fake)

    result = backend.read("foo.txt", offset=0, limit=10)

    assert isinstance(result, ReadResult)
    # "line-one\nline-two\n".split("\n") == ["line-one", "line-two", ""]
    assert result.lines == ["line-one", "line-two", ""]
    assert result.start_line == 1
    fake.read_text.assert_called_once()


def test_read_keeps_trailing_blank_lines(tmp_path):
    """bwrap 路径下 ``split("\\n")`` 往返无损：末尾空行不被吞掉。"""
    fake = MagicMock()
    fake.read_text.return_value = "x\n\n"
    backend = _bwrap_backend(tmp_path, bwrap=fake)

    result = backend.read("foo.txt", offset=0, limit=10)

    assert isinstance(result, ReadResult)
    assert result.lines == ["x", "", ""]
    assert "\n".join(result.lines).split("\n") == result.lines


def test_read_offset_and_limit(tmp_path):
    """bwrap 路径下 offset/limit 语义与 start_line 一致。"""
    fake = MagicMock()
    fake.read_text.return_value = "a\nb\nc\n"
    backend = _bwrap_backend(tmp_path, bwrap=fake)

    result = backend.read("foo.txt", offset=1, limit=2)

    assert isinstance(result, ReadResult)
    # "a\nb\nc\n".split("\n") == ["a","b","c",""] ⇒ idx 1 起取 2 行 ⇒ ["b","c"]
    assert result.lines == ["b", "c"]
    assert result.start_line == 2


def test_read_segment_is_single_empty_line(tmp_path):
    """bwrap 路径下片段为单个空行时 lines == [""]。"""
    fake = MagicMock()
    fake.read_text.return_value = "a\n\nb"
    backend = _bwrap_backend(tmp_path, bwrap=fake)

    result = backend.read("foo.txt", offset=1, limit=1)

    assert isinstance(result, ReadResult)
    assert result.lines == [""]
    assert result.start_line == 2


def test_read_missing_file_is_diagnostic_string(tmp_path):
    """bwrap 读不到文件时仍是 str 返回型诊断。"""
    fake = MagicMock()
    fake.read_text.return_value = None
    backend = _bwrap_backend(tmp_path, bwrap=fake)

    result = backend.read("foo.txt")

    assert isinstance(result, str)
    assert "not found" in result


def test_read_empty_file_is_diagnostic_string(tmp_path):
    """bwrap 读到空文件时仍是 str 提示。"""
    fake = MagicMock()
    fake.read_text.return_value = ""
    backend = _bwrap_backend(tmp_path, bwrap=fake)

    result = backend.read("foo.txt")

    assert isinstance(result, str)
    assert "文件存在但内容为空" in result


def test_read_offset_overflow_is_diagnostic_string(tmp_path):
    """bwrap 路径下偏移越界也是 str 返回型诊断。"""
    fake = MagicMock()
    fake.read_text.return_value = "only"
    backend = _bwrap_backend(tmp_path, bwrap=fake)

    result = backend.read("foo.txt", offset=50)

    assert isinstance(result, str)
    assert "exceeds file length" in result


def test_read_denied_path_is_diagnostic_string(tmp_path):
    """bwrap 路径下敏感路径拒绝是 str 返回型诊断。"""
    fake = MagicMock()
    backend = _bwrap_backend(tmp_path, bwrap=fake)

    result = backend.read("/root/.ssh/id_rsa")

    assert isinstance(result, str)
    assert "拒绝访问敏感路径" in result
    fake.read_text.assert_not_called()


def test_read_has_no_transform_parameter(tmp_path):
    """第一版透传给 bwrap 路径的 transform 回调已移除。"""
    params = inspect.signature(BubblewrapFilesystemBackend.read).parameters
    assert "transform" not in params


def test_write_routes_to_bwrap(tmp_path):
    """write 走 bwrap 子进程（不落宿主机）。"""
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path))
    fake = MagicMock()
    fake.write_text.return_value = True
    backend._write_text = fake.write_text

    result = backend.write("bar.txt", "payload")
    assert result.error is None
    fake.write_text.assert_called_once()
    # 内容经 bwrap 写入，宿主机不应直接落盘（此处为 mock，故不存在）
    assert not (tmp_path / "bar.txt").exists()


def test_execute_routes_to_bwrap(tmp_path):
    """execute 走 bwrap 子进程。"""
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path))
    fake = MagicMock()
    fake.run_shell.return_value = BwrapResult(output="ok", exit_code=0)
    backend._run_shell = fake.run_shell

    result = backend.execute("echo hi", timeout=10, max_output_size=1000)
    assert result.output == "ok"
    assert result.exit_code == 0
    fake.run_shell.assert_called_once_with("echo hi", timeout=10)


async def test_aexecute_routes_to_bwrap(tmp_path):
    """aexecute 委托到同步 execute（bwrap 子进程）。"""
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path))
    fake = MagicMock()
    fake.run_shell.return_value = BwrapResult(output="ok", exit_code=0)
    backend._run_shell = fake.run_shell

    result = await backend.aexecute("echo hi", timeout=10, max_output_size=1000)
    assert result.output == "ok"
    assert result.exit_code == 0
    fake.run_shell.assert_called_once_with("echo hi", timeout=10)


def test_ls_routes_to_bwrap(tmp_path):
    """ls_info 走 bwrap 子进程。"""
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path))
    fake = MagicMock()
    fake.list_entries.return_value = [
        {"path": str(tmp_path / "a.py"), "is_dir": False, "size": 12, "modified_at": "2026-01-01T00:00:00"},
        {"path": str(tmp_path / "sub"), "is_dir": True, "size": 0, "modified_at": "2026-01-01T00:00:00"},
    ]
    backend._list_entries = fake.list_entries

    result = backend.ls_info("/")
    assert len(result) == 2
    # 目录路径带 '/' 后缀
    paths = {r["path"] for r in result}
    assert any(p.endswith("/") for p in paths)
    fake.list_entries.assert_called_once()


def test_upload_routes_to_bwrap(tmp_path):
    """upload_files 走 bwrap 子进程（bytes 经 stdin）。"""
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path))
    fake = MagicMock()
    fake.write_bytes.return_value = True
    backend._write_bytes = fake.write_bytes

    result = backend.upload_files([("foo.bin", b"\x00\x01\x02")])
    assert result[0]["error"] is None
    fake.write_bytes.assert_called_once()
    assert not (tmp_path / "foo.bin").exists()  # 内容经 bwrap 写入，宿主机不直接落盘


def test_download_routes_to_bwrap(tmp_path):
    """download_files 走 bwrap 子进程（bytes 二进制）。"""
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path))
    fake = MagicMock()
    fake.read_bytes.return_value = b"\x00\x01\x02"
    backend._read_bytes = fake.read_bytes

    result = backend.download_files(["foo.bin"])
    assert result[0]["content"] == b"\x00\x01\x02"
    assert result[0]["error"] is None
    fake.read_bytes.assert_called_once()


def test_grep_raw_no_host_fallback_when_rg_unavailable(tmp_path):
    """沙箱内 rg 不可用时直接返回 []，不回退宿主机搜索（避免隐含逃逸）。"""
    (tmp_path / "leak.txt").write_text("SECRET_TOKEN=abc")
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path))
    fake = MagicMock()
    fake.grep.return_value = None
    backend._grep = fake.grep

    result = backend.grep_raw("SECRET_TOKEN", "/")

    assert result == []
    fake.grep.assert_called_once()


def test_grep_raw_maps_to_virtual_paths(tmp_path):
    """沙箱 rg 命中经虚拟路径映射返回 GrepMatch（virtual_mode 下去 cwd 前缀）。"""
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)
    fake = MagicMock()
    fake.grep.return_value = [(str(tmp_path / "a.txt"), 3, "hit")]
    backend._grep = fake.grep

    result = backend.grep_raw("hit", "/")

    assert result == [{"path": "/a.txt", "line": 3, "text": "hit"}]


def test_save_load_roundtrip(tmp_path):
    """save/load 与同进程后端同构（root_dir/virtual_mode/max_file_size_mb）。"""
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path), virtual_mode=True, max_file_size_mb=7)
    payload = backend.save()
    assert payload["virtual_mode"] is True
    assert payload["max_file_size_mb"] == 7

    other = BubblewrapFilesystemBackend(root_dir="/tmp")
    other.load(payload)
    assert other.virtual_mode is True
    assert other.max_file_size_bytes == 7 * 1024 * 1024
