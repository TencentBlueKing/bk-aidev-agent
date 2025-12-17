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

import os

from aidev_bkplugin.packages.opentelemetry.utils import get_otel_endpoints, get_env_bool


class OTelConfig:
    """OTel 上报配置"""

    def __init__(self):
        # ===== 基础配置 =====
        self.enabled: bool = get_env_bool("BKAI_AGENT_OTEL_ENABLED", True)
        self.debug: bool = get_env_bool("BKAI_AGENT_OTEL_DEBUG", False)

        # ===== OTEL Endpoint 配置 =====
        self.service_name: str = os.getenv("BKPAAS_APP_ID", "") or os.getenv("BKPAAS_APP_CODE", "aidev-agent")
        # ===== OTel Endpoint 地址(支持多个) =====
        self.otel_endpoints: list[dict] = get_otel_endpoints()

        # ===== 功能开关 =====
        self.enable_traces: bool = get_env_bool("BKAI_AGENT_ENABLE_TRACES", True)
        self.enable_metrics: bool = get_env_bool("BKAI_AGENT_ENABLE_METRICS", False)
        self.enable_logs: bool = get_env_bool("BKAI_AGENT_ENABLE_LOGS", False)

        # ===== 性能优化配置 =====
        # 最大字符串长度限制
        self.max_attribute_length: int = int(os.getenv("BKAI_AGENT_MAX_ATTRIBUTE_LENGTH", "10000"))

    def __repr__(self) -> str:
        endpoints_summary = f"{len(self.otel_endpoints)} endpoint(s)"
        if self.otel_endpoints:
            endpoints_summary += f": {', '.join(ep['url'] for ep in self.otel_endpoints)}"

        return (
            f"OTelConfig("
            f"enabled={self.enabled}, "
            f"service_name={self.service_name}, "
            f"otel_endpoints={endpoints_summary}, "
            f"enable_traces={self.enable_traces})"
        )


# 默认配置实例
default_config = OTelConfig()
