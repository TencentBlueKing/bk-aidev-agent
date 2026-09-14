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

安全能力原语集合。

本包承载各类安全检测原语与子包，全部以**纯函数 / 纯数据**形式提供，由调用方
（``core`` 层的 wrapper、middleware 与 sandbox backend）直接调用：

- ``file_safety`` —— 敏感路径判定（``deny_reason``）；
- ``threat_patterns`` —— 注入 / 数据外泄检测与不可信内容包裹；
- :mod:`~aidev_agent.packages.security.command` —— 命令执行安全四件套与编排入口；
- :mod:`~aidev_agent.packages.security.redaction` —— 敏感信息脱敏。

依赖方向：本包只允许依赖标准库 / pydantic / langchain_core / ``pydantic_models`` /
本包内模块，禁止 ``from aidev_agent.core`` / ``from aidev_agent.services`` / ``from aidev_agent.api``。
"""

from __future__ import annotations

__all__: list[str] = []
