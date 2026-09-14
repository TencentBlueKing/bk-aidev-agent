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

from pydantic import BaseModel, Field

from aidev_agent.config import settings


class ToolNodeSettings(BaseModel):
    """ToolNode wrappers settings.

    安全相关字段（use_tool_redaction / use_tool_untrusted_sanitize / use_result_limit）默认取
    安全开启态，最终值由 ``ReActAgentBuilder`` 在 graph 装配层从 ``SecuritySettings`` 拆解后注入。
    本类不持有 ``SecuritySettings`` 对象、也不直接读取环境变量。

    - ``use_tool_redaction``：结果脱敏（所有工具结果按 MODEL_OUTPUT purpose 掩码凭据）。
    - ``use_tool_untrusted_sanitize``：不可信工具结果净化（原型污染清理 + 注入扫描 + 包裹）。
    """

    use_timer: bool = True
    use_result_limit: bool = True
    result_limit_thrd: int = Field(default=settings.TOOL_RESULT_LIMIT_THRD, ge=1, description="结果长度限制阈值")
    use_json_repair_on_error: bool = True
    use_tool_redaction: bool = True
    use_tool_untrusted_sanitize: bool = True
