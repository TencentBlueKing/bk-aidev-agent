# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.command

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

命令执行安全四件套（聚合子包）。

收拢命令执行侧的四层安全能力：

- ``command_security`` —— 命令允许列表（Layer 0，默认拒绝）+ 文件路径校验；
- ``command_blocklist`` —— 危险命令黑名单（Layer 1，命中即硬拒绝）；
- ``command_approval`` —— 命令级审批（Layer 2，``command_review_disposition="approval"`` 的 HITL）；
- ``command_risk_assessor`` —— review 处置前的智能预分流评估器（``enable_command_review_auto``，辅助 LLM 三级预分流）。

本子包同时承载命令执行前后的**编排**入口 ``enforce_command_security``
（三层防护：黑名单 → 允许列表 → 命令级审批），供 ``core.tools.runtime_tools``
的 execute 工具调用。

本子包只做公开接口聚合转发，具体实现仍分别在各自模块中；依赖方向沿用
``packages.security`` 约定：仅标准库 / pydantic / langchain_core / ``pydantic_models`` / 本包内模块。
"""

from __future__ import annotations

from .command_definitions import (
    CommandFinding,
    CommandReport,
    CommandSource,
    CommandStructureFinding,
    CommandVerdict,
    RuleResult,
)
from .command_risk_assessor import (
    CommandRiskAssessor,
    RiskAssessment,
)
from .command_security import (
    enforce_command_security,
    validate_path,
)

# ``__all__`` 的收录口径：**存在包外生产消费方**的符号，外加这类符号的**配套类型**
# （返回值的结构类型 —— 包外要有能力为返回值写类型注解，否则该 API 不可用）。
#
# 刻意**不**收录「包外当前无人使用」的规则数据表与未接线入口
# （``ALLOWED_COMMANDS`` / ``BLOCKLIST_*`` / ``validate_command`` /
# ``require_command_approval`` 等）：它们各自仍定义在子模块里、属性访问照常，
# 但「无人用却声明为公开」是一份会漂移的弱清单 —— 需要时应先有真实消费方。
# 测试大量经**子模块路径**引用这些名字（白盒），不构成「包级导出」的消费方。
__all__ = [
    # 结果类型（validate_command 的返回结构；包外需据此写类型注解）
    "CommandReport",
    "CommandFinding",
    "CommandStructureFinding",
    "CommandSource",
    "CommandVerdict",
    "RuleResult",
    # 校验与防护入口
    "validate_path",
    "enforce_command_security",
    # 命令风险评估入口 + 其返回类型
    "CommandRiskAssessor",
    "RiskAssessment",
]
