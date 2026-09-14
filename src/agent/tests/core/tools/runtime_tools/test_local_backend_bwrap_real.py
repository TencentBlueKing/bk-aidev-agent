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

真实 bwrap 端到端测试（非 mock）。bwrap 二进制不可用或 user namespace 被禁时
自动 skip，保证 CI 无 bwrap 环境不红。
"""

from __future__ import annotations

import shutil

import pytest
from aidev_agent.core.tools.runtime_tools.bubblewrap_backend import BubblewrapFilesystemBackend
from aidev_agent.core.tools.runtime_tools.types import ReadResult


def _bwrap_usable() -> bool:
    if shutil.which("bwrap") is None:
        return False
    try:
        return BubblewrapFilesystemBackend(root_dir="/tmp", bwrap_readonly_paths="/usr").is_available()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _bwrap_usable(), reason="bwrap 不可用，跳过真实隔离测试")


def _make_backend(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    backend = BubblewrapFilesystemBackend(root_dir=str(ws))
    assert backend._available, "bwrap 应可用"
    return ws, backend


def test_real_read_workspace_file(tmp_path):
    ws, backend = _make_backend(tmp_path)
    (ws / "hello.txt").write_text("hello world\n")
    result = backend.read("hello.txt", offset=0, limit=10)
    assert isinstance(result, ReadResult)
    # "hello world\n".split("\n") == ["hello world", ""]（split 保留末尾空元素）
    assert result.lines == ["hello world", ""]
    assert result.start_line == 1


def test_real_read_system_file_blocked(tmp_path):
    """沙箱内 /etc 不可见：读 /etc/passwd 应失败。"""
    _, backend = _make_backend(tmp_path)
    content = backend.read("/etc/passwd", offset=0, limit=10)
    assert "not found" in content.lower()


def test_real_write_workspace_file(tmp_path):
    ws, backend = _make_backend(tmp_path)
    result = backend.write("new.txt", "payload")
    assert result.error is None
    assert (ws / "new.txt").read_text() == "payload"


def test_real_upload_download_bytes(tmp_path):
    ws, backend = _make_backend(tmp_path)
    payload = b"\x00\x01\x02\xffbinary"
    up = backend.upload_files([("bin.dat", payload)])
    assert up[0]["error"] is None
    assert (ws / "bin.dat").read_bytes() == payload
    dl = backend.download_files(["bin.dat"])
    assert dl[0]["error"] is None
    assert dl[0]["content"] == payload


def test_real_execute_system_file_blocked(tmp_path):
    """execute 在沙箱内执行，/etc 不可见（cat /etc/passwd 失败）。"""
    _, backend = _make_backend(tmp_path)
    res = backend.execute("cat /etc/passwd", timeout=10, max_output_size=1000)
    assert res.exit_code != 0
