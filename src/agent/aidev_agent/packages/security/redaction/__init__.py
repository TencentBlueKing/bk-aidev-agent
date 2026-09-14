# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.redaction

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

敏感信息脱敏（聚合子包）。

分层框架：**已知 secret 精确值为主 → 结构化检测为辅 → 裸熵兜底**。
本子包承载出口语义（``RedactionPurpose``）、命中模型（``Finding`` / ``ScanResult``）、
掩码策略（``MaskStyle``）、已知值注入式 detector 与 detector 管线。

**已知值无模块级注册表**：已知敏感值经 ``SecurityRedactionSettings.known_sensitive_values``
随 ``settings`` 传入（``scan_text(settings=...)``），由 ``_detectors_for_scan`` 就地
构造 ``RegisteredSecretDetector``；redaction 不持有任何模块级可变全局状态 ——
env / backend 的解析留在调用方。

**已知值只有一个出口**：已知敏感值经 ``SecurityRedactionSettings.known_sensitive_values``
随 ``settings`` 传入（``scan_text(settings=...)``），由 ``_detectors_for_scan`` 就地
构造 ``RegisteredSecretDetector``，与其它命中一起在 detector 管线中按 ``priority``
决策并统一用 ``masking.REDACT_PLACEHOLDER``。历史上另有一条独立的「已知值精确替换」
出口（``redact_known_values`` + legacy ``KNOWN_VALUES_PLACEHOLDER``），因与本管线
共用同一匹配机制却只改文案、且已无调用点，已删除。

本子包只做公开接口聚合转发，具体实现仍分别在各自模块中；依赖方向沿用
``packages.security`` 约定：仅标准库 / pydantic / langchain_core /
``pydantic_models`` / 本包内模块。
``redaction/`` 是纯叶子包 —— 禁止 import ``aidev_agent.core`` / ``services`` / ``api``。
"""

from __future__ import annotations

from aidev_agent.packages.security.redaction.findings import (
    Finding,
    ScanResult,
    merge_spans,
)
from aidev_agent.packages.security.redaction.masking import (
    REDACT_PLACEHOLDER,
    mask,
)
from aidev_agent.packages.security.redaction.operations import (
    count_sensitive_hits,
    redact_for_export,
    redact_payload,
    redact_text,
    scan_text,
)
from aidev_agent.packages.security.redaction.policy import (
    MaskStyle,
    RedactionPurpose,
    mask_style_for,
)

__all__ = [
    # 出口语义 / 掩码风格
    "RedactionPurpose",
    "MaskStyle",
    "mask_style_for",
    # 命中模型 / span 合并
    "Finding",
    "ScanResult",
    "merge_spans",
    # 掩码
    "mask",
    "REDACT_PLACEHOLDER",
    # 脱敏编排（公开 API）
    "redact_text",
    "redact_payload",
    "scan_text",
    "count_sensitive_hits",
    "redact_for_export",
]
