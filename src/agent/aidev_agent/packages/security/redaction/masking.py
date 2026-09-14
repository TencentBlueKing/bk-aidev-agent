# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.redaction.masking

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

两种掩码风格（partial / typed_sentinel）与统一占位符常量。

``partial`` 的保留首尾阈值修正为 **32**：短 secret 保留首尾等于没脱敏
（例：``sk-abcd`` → ``sk-a...bcd`` 基本等于全泄露），故 ``len < 32`` 一律整体替换。
历史实现的阈值是 ``len <= 10``，与「短值整体替换、长值保留首尾」的意图不符。

**阈值可配置（T-urf-03）**：``partial`` 的三个阈值（``partial_min_len`` /
``partial_head`` / ``partial_tail``）**不再硬编码在本模块** —— 由调用方
（``redaction.operations``）从 ``SecurityRedactionSettings`` 的 ``redact_partial_min_len`` /
``redact_partial_head`` / ``redact_partial_tail`` 派生并**显式传入**。
``SecurityRedactionSettings`` 三个字段的默认值是 32 / 6 / 4，与历史硬编码常量一致，
故默认路径**逐字节等价**。

``mask()`` 的三个阈值参数是**仅关键字且必填无默认** —— 这是刻意的：参数化但
没人传值等于没参数化，且默认值会让「忘了传」静默使用旧阈值。
必填 ⇒ 遗漏即 ``TypeError``，不会静默削弱脱敏。

**``REDACT_PLACEHOLDER`` 与 ``mask()`` 产出的字符串不同**：
``REDACT_PLACEHOLDER`` 是 ``[REDACTED]``（无 kind 后缀），而 ``mask()`` 产出
``[REDACTED:{kind}]``。本常量当前**不被 ``mask()`` 读取**（``mask`` 直接构造
f-string），是独立的对外常量，被 ``redaction/__init__.py`` 导出、被
``tests/.../test_masking.py`` 断言 —— 删除它属「对外接口移除」，超出本次重构范围，故保留。

公开接口：``REDACT_PLACEHOLDER`` / ``mask``。
"""

from __future__ import annotations

from aidev_agent.packages.security.redaction.policy import MaskStyle

# 统一脱敏占位符（随 D-12 从 redact.py 迁入本模块）
REDACT_PLACEHOLDER = "[REDACTED]"


def mask(
    value: str,
    *,
    kind: str,
    style: MaskStyle,
    partial_min_len: int,
    partial_head: int,
    partial_tail: int,
) -> str:
    """按风格掩码单个命中值。

    Args:
        value: 命中到的原文片段。
        kind: 凭据类型标签（用于 typed sentinel）。
        style: 掩码风格。
        partial_min_len: partial 风格保留首尾的最小长度：``len(value) >= 该值`` 才保留
            首尾，否则整体替换。无默认值，由 ``SecurityRedactionSettings.redact_partial_min_len``
            派生后必填传入（其字段默认值为 32）。
        partial_head: partial 风格保留的首部字符数（常含厂商前缀）。无默认值，由
            ``SecurityRedactionSettings.redact_partial_head`` 派生后必填传入（其字段默认值为 6）。
        partial_tail: partial 风格保留的尾部字符数。无默认值，由
            ``SecurityRedactionSettings.redact_partial_tail`` 派生后必填传入（其字段默认值为 4）。

    Returns:
        掩码后的文本。
    """
    if style is MaskStyle.TYPED_SENTINEL:
        return f"[REDACTED:{kind}]"
    # style is MaskStyle.PARTIAL
    if len(value) >= partial_min_len:
        return f"{value[:partial_head]}...{value[-partial_tail:]}"
    # 短值保留首尾等于没脱敏 → 整体替换
    return f"[REDACTED:{kind}]"


__all__ = [
    # 占位符常量
    "REDACT_PLACEHOLDER",
    # 掩码
    "mask",
]
