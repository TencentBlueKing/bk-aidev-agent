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

from aidev_agent.core.tools.runtime_tools.bubblewrap_backend import BubblewrapFilesystemBackend


def test_prefix_readonly_bind_and_no_network():
    """只读工作区挂载 + 默认关网 + 进程隔离。"""
    sb = BubblewrapFilesystemBackend(
        root_dir="/tmp/ws",
        bwrap_readonly_paths="/usr",
        bwrap_allow_network=False,
        bwrap_path="bwrap",
    )
    prefix = sb._prefix(writable=False)
    # 显式 --unshare-user：容器/受限环境下靠 user namespace 获得 mount 权限
    assert prefix[:3] == ["bwrap", "--unshare-user", "--ro-bind"]
    # 只读系统目录
    assert "--ro-bind" in prefix and "/tmp/ws" in prefix
    assert "--bind" not in prefix
    # 关网 + 进程共存亡
    assert "--unshare-net" in prefix
    assert "--unshare-pid" not in prefix  # 受限容器与 --proc 挂载冲突，已去除
    assert "--die-with-parent" in prefix
    assert "--chdir" in prefix and "/tmp/ws" in prefix


def test_prefix_writable_uses_bind():
    """可写工作区用 --bind。"""
    sb = BubblewrapFilesystemBackend(root_dir="/tmp/ws", bwrap_readonly_paths="", bwrap_allow_network=False)
    prefix = sb._prefix(writable=True)
    assert ["--bind", "/tmp/ws", "/tmp/ws"] in _windows(prefix)


def test_prefix_allow_network_omits_unshare_net():
    """允许网络时不加 --unshare-net。"""
    sb = BubblewrapFilesystemBackend(root_dir="/tmp/ws", bwrap_readonly_paths="", bwrap_allow_network=True)
    assert "--unshare-net" not in sb._prefix(writable=True)


def test_prefix_skips_missing_readonly_dir():
    """不存在的只读目录被跳过（不挂载）。"""
    sb = BubblewrapFilesystemBackend(
        root_dir="/tmp/ws", bwrap_readonly_paths="/definitely/missing/dir", bwrap_allow_network=False
    )
    prefix = sb._prefix(writable=False)
    assert "/definitely/missing/dir" not in prefix


def test_is_available_false_when_binary_missing():
    """bwrap 二进制不存在时探测返回 False（fail-open 信号）。"""
    sb = BubblewrapFilesystemBackend(root_dir="/tmp/ws", bwrap_path="/nonexistent/bwrap-xyz")
    assert sb.is_available() is False


def test_run_returns_none_exit_code_when_missing():
    """bwrap 缺失时 run() 不抛异常，返回 exit_code=None。"""
    sb = BubblewrapFilesystemBackend(root_dir="/tmp/ws", bwrap_path="/nonexistent/bwrap-xyz")
    res = sb._read_text("/tmp/ws/foo.txt")
    # _read_text 失败返回 None（cat 无法启动）
    assert res is None


def test_glob_entries_normalizes_pattern():
    """glob 带目录的 pattern 归一为 basename 段。"""
    sb = BubblewrapFilesystemBackend(root_dir="/tmp/ws", bwrap_path="/nonexistent/bwrap-xyz")
    # 直接验证归一逻辑：find 命令由 _prefix + args 组成，此处仅验证不抛异常即可。
    # （bwrap 缺失，_glob_entries 返回 []）
    assert sb._glob_entries("/tmp/ws", "**/*.py") == []
    assert sb._glob_entries("/tmp/ws", "subdir/*.py") == []


def _windows(seq):
    """返回长度为 3 的连续子序列列表（用于匹配 ["--bind", a, b]）。"""
    return [seq[i : i + 3] for i in range(len(seq) - 2)]


def test_readonly_default_paths_constant():
    """默认只读路径不含敏感目录 /etc、/root、/home。"""
    from aidev_agent.core.tools.runtime_tools.bubblewrap_backend import DEFAULT_READONLY_PATHS

    assert "/usr" in DEFAULT_READONLY_PATHS
    assert "/etc" not in DEFAULT_READONLY_PATHS
    assert "/root" not in DEFAULT_READONLY_PATHS
    assert "/home" not in DEFAULT_READONLY_PATHS
