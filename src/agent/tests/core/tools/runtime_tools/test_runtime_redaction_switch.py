# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from __future__ import annotations

from aidev_agent.core.tools.runtime_tools.provider import (
    RuntimeBackendResolver,
    _runtime_redactor,
)
from aidev_agent.pydantic_models import SecuritySettings

_SECRET = "token sk-" + "a" * 36


class _StubBackend:
    """仅满足 ``_get_sensitive_values`` 的 getattr 访问（无额外敏感值）。"""


def test_tool_redaction_off_yields_identity_redactor():
    """``enable_tool_redaction=False`` 时 runtime 出口返回恒等 redactor，不改动内容。"""
    resolver = RuntimeBackendResolver(security_settings=SecuritySettings(enable_tool_redaction=False))
    _, redact = _runtime_redactor(resolver, _StubBackend())
    assert redact(_SECRET) == _SECRET
    # 兼容 handler 传入的 preserve_line_breaks 关键字
    assert redact(_SECRET, preserve_line_breaks=True) == _SECRET


def test_tool_redaction_on_redacts_vendor_token():
    """默认开启时 runtime 出口正常脱敏（对照组，证明上一条的恒等来自开关而非路径不可达）。"""
    resolver = RuntimeBackendResolver(security_settings=SecuritySettings())
    _, redact = _runtime_redactor(resolver, _StubBackend())
    assert redact(_SECRET) != _SECRET


def test_no_security_settings_redacts_by_default():
    """未注入 security_settings 时维持原行为（默认脱敏）。"""
    resolver = RuntimeBackendResolver(security_settings=None)
    _, redact = _runtime_redactor(resolver, _StubBackend())
    assert redact(_SECRET) != _SECRET
