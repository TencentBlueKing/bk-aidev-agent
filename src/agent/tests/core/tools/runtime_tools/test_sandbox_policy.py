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
from aidev_agent.pydantic_models import SandboxMode, SandboxPolicy


def test_sandbox_policy_defaults():
    """SandboxPolicy 默认值：workspace_write 模式、关网、降权、只读系统目录。"""
    p = SandboxPolicy()
    assert p.mode is SandboxMode.WORKSPACE_WRITE
    assert "/usr" in p.readonly_paths
    assert "/bin" in p.readonly_paths
    assert "/etc" not in p.readonly_paths
    assert "/root" not in p.readonly_paths
    assert "/home" not in p.readonly_paths
    assert p.allow_network is False
    assert p.drop_privileges is True
    assert p.deny_paths == []


def test_sandbox_policy_custom_deny_and_domains():
    """自定义策略：deny_paths + 网络白名单域名。"""
    p = SandboxPolicy(
        mode=SandboxMode.READONLY,
        deny_paths=["/etc/ssh", "/root/.ssh"],
        allow_network=True,
        allow_network_domains=["*.example.com"],
    )
    assert p.mode is SandboxMode.READONLY
    assert p.deny_paths == ["/etc/ssh", "/root/.ssh"]
    assert p.allow_network is True
    assert p.allow_network_domains == ["*.example.com"]


def test_prefix_translates_policy():
    """后端 _prefix 把策略翻译为 bwrap 前缀。"""
    policy = SandboxPolicy(readonly_paths=["/usr"], allow_network=False)
    backend = BubblewrapFilesystemBackend(sandbox_policy=policy, bwrap_path="bwrap")
    prefix = backend._prefix(writable=False)
    assert prefix[:3] == ["bwrap", "--unshare-user", "--ro-bind"]
    assert "--unshare-net" in prefix
    assert "--die-with-parent" in prefix
    assert "--unshare-pid" not in prefix  # 受限容器与 --proc 挂载冲突，已去除


def test_prefix_allow_network_omits_unshare_net():
    """allow_network=True 时不加 --unshare-net。"""
    policy = SandboxPolicy(allow_network=True)
    backend = BubblewrapFilesystemBackend(sandbox_policy=policy, bwrap_path="bwrap")
    assert "--unshare-net" not in backend._prefix(writable=True)


def test_prefix_skips_missing_readonly_dir():
    """不存在的只读目录被后端跳过（不挂载）。"""
    policy = SandboxPolicy(readonly_paths=["/definitely/missing/dir"])
    backend = BubblewrapFilesystemBackend(sandbox_policy=policy, bwrap_path="bwrap")
    assert "/definitely/missing/dir" not in backend._prefix(writable=False)


def test_backend_accepts_policy():
    """backend 接受 sandbox_policy 参数，_prefix 按该策略组装。"""
    policy = SandboxPolicy(readonly_paths=[], allow_network=False)
    sb = BubblewrapFilesystemBackend(root_dir="/tmp/ws", sandbox_policy=policy, bwrap_path="bwrap")
    prefix = sb._prefix(writable=True)
    assert prefix[:2] == ["bwrap", "--unshare-user"]
    assert ["--bind", "/tmp/ws", "/tmp/ws"] in _windows(prefix)
    # model_copy 隔离：传入的 policy 不被后端内部降级污染
    assert sb._policy is not policy


def test_backend_legacy_params_still_work():
    """旧接口（bwrap_readonly_paths/bwrap_allow_network）仍工作，内部转成 policy。"""
    sb = BubblewrapFilesystemBackend(root_dir="/tmp/ws", bwrap_readonly_paths="/usr", bwrap_allow_network=False)
    assert sb._policy.readonly_paths == ["/usr"]
    assert sb._policy.allow_network is False


def _windows(seq):
    """返回长度为 3 的连续子序列列表（用于匹配 ["--bind", a, b]）。"""
    return [seq[i : i + 3] for i in range(len(seq) - 2)]
