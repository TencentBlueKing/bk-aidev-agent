# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.redaction.policy

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

脱敏出口语义（``RedactionPurpose``）与掩码风格（``MaskStyle``）。

历史实现用 ``force: bool`` 承载三种语义（忽略开关 / 严格出口 / 掩码方式），
调用点只能硬编码 ``force=True``，语义不可读。
本模块把「出口」显式化为枚举，并按出口查表得出掩码风格。

公开接口：``RedactionPurpose`` / ``MaskStyle`` / ``mask_style_for``。
"""

from __future__ import annotations

from enum import Enum


class RedactionPurpose(str, Enum):
    """脱敏出口语义（取代历史 ``force: bool``）。

    - ``LOG``：日志落库 / 审计摘要
    - ``MODEL_OUTPUT``：进入模型上下文（工具结果）
    - ``FILE_READ``：文件读取给模型看
    - ``EXPORT``：导出 / 上报，最严格
    """

    LOG = "log"
    MODEL_OUTPUT = "model_output"
    FILE_READ = "file_read"
    EXPORT = "export"


class MaskStyle(str, Enum):
    """掩码风格。

    - ``PARTIAL``：长值保留首尾（便于识别泄露来源）
    - ``TYPED_SENTINEL``：不保留 secret body，只留类型标签
    """

    PARTIAL = "partial"
    TYPED_SENTINEL = "typed_sentinel"


# 出口 → 掩码风格映射（LOG/EXPORT 保留首尾；进模型上下文的出口不保留 body）
_PURPOSE_MASK_STYLE: dict[RedactionPurpose, MaskStyle] = {
    RedactionPurpose.LOG: MaskStyle.PARTIAL,
    RedactionPurpose.EXPORT: MaskStyle.PARTIAL,
    RedactionPurpose.MODEL_OUTPUT: MaskStyle.TYPED_SENTINEL,
    RedactionPurpose.FILE_READ: MaskStyle.TYPED_SENTINEL,
}


def mask_style_for(purpose: RedactionPurpose) -> MaskStyle:
    """按出口语义查表得出掩码风格。

    未知 purpose 回落 ``TYPED_SENTINEL``（fail-closed 方向：不保留 secret body）。
    """
    return _PURPOSE_MASK_STYLE.get(purpose, MaskStyle.TYPED_SENTINEL)


__all__ = [
    # 出口语义
    "RedactionPurpose",
    # 掩码风格
    "MaskStyle",
    "mask_style_for",
]
