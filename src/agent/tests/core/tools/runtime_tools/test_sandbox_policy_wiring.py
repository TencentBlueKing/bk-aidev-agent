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
from aidev_agent.pydantic_models import SandboxMode, SandboxPolicy, SecuritySettings


def test_security_settings_direct_construction_parses_sandbox_policy_dict():
    """平台下发 sandbox_policy dict 时，直接构造自动解析为 SandboxPolicy。"""
    ss = SecuritySettings(
        sandbox_policy={
            "mode": "readonly",
            "deny_paths": ["/etc/ssh", "/root/.ssh"],
            "allow_network": False,
        }
    )
    assert isinstance(ss.sandbox_policy, SandboxPolicy)
    assert ss.sandbox_policy.mode is SandboxMode.READONLY
    assert ss.sandbox_policy.deny_paths == ["/etc/ssh", "/root/.ssh"]
    assert ss.sandbox_policy.allow_network is False


def test_security_settings_direct_construction_none_sandbox_policy():
    """未下发 sandbox_policy 时保持 None（沙箱不启用）。"""
    ss = SecuritySettings()
    assert ss.sandbox_policy is None


def test_security_settings_direct_construction_keeps_other_fields():
    """下发 sandbox_policy 不干扰其他安全字段解析。"""
    ss = SecuritySettings(enable_tool_redaction=False, sandbox_policy={"mode": "full_access"})
    assert ss.enable_tool_redaction is False
    assert isinstance(ss.sandbox_policy, SandboxPolicy)
    assert ss.sandbox_policy.mode is SandboxMode.FULL_ACCESS


def test_bubblewrap_backend_accepts_sandbox_policy(tmp_path):
    """BubblewrapFilesystemBackend 接收 sandbox_policy，持有隔离后的策略副本。"""
    policy = SandboxPolicy(readonly_paths=[], deny_paths=["/etc/ssh"])
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path), sandbox_policy=policy)
    # model_copy 隔离：内容一致但非同一对象
    assert backend._policy.readonly_paths == policy.readonly_paths
    assert backend._policy.deny_paths == ["/etc/ssh"]
    assert backend._policy is not policy


def test_bubblewrap_backend_always_constructs_policy(tmp_path):
    """sandbox_policy 非 None 时按该策略构造（无 bwrap_enabled 开关）。"""
    backend = BubblewrapFilesystemBackend(
        root_dir=str(tmp_path),
        sandbox_policy=SandboxPolicy(),
    )
    assert backend._policy.readonly_paths == SandboxPolicy().readonly_paths


def test_bubblewrap_backend_default_policy_when_no_sandbox_policy(tmp_path):
    """未下发 sandbox_policy 时回落 bwrap_readonly_paths / bwrap_allow_network。"""
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path), bwrap_readonly_paths="/usr")
    assert backend._policy.readonly_paths == ["/usr"]
    assert backend._policy.allow_network is False
