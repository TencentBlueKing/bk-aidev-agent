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

from aidev_agent.config import settings as agent_settings

from .utils import get_env_bool


class OTelConfig:
    """OTel 上报配置"""

    def __init__(self, otel_endpoints: list[dict] | None = None):
        # ===== 基础配置 =====
        self.enabled: bool = get_env_bool("BKAI_AGENT_OTEL_ENABLED", True)
        self.debug: bool = get_env_bool("BKAI_AGENT_OTEL_DEBUG", False)

        # ===== OTEL Endpoint 配置 =====
        self.service_name: str = os.getenv("BKPAAS_APP_ID", "") or os.getenv("BKPAAS_APP_CODE", "aidev-agent")
        # ===== OTel Endpoint 地址(支持多个,由调用方注入) =====
        self.otel_endpoints: list[dict] = otel_endpoints if otel_endpoints is not None else []

        # ===== 功能开关 =====
        self.enable_traces: bool = get_env_bool("BKAI_AGENT_ENABLE_TRACES", True)
        self.enable_metrics: bool = bool(agent_settings.BKAI_AGENT_ENABLE_METRICS)
        # bkplugin may install a BKM-specific MeterProvider while the Agent SDK keeps metric instrumentation enabled.
        self.metric_provider_managed_externally: bool = False
        self.metric_export_interval_millis: int = max(1000, int(os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "60000")))
        self.metric_export_timeout_millis: int = max(1000, int(os.getenv("OTEL_METRIC_EXPORT_TIMEOUT", "30000")))
        self.enable_logs: bool = get_env_bool("BKAI_AGENT_ENABLE_LOGS", False)
        # ``logging`` 用于本地调试：仍生成完整 trace/span，但只写应用日志，
        # 不创建任何远程 OTLP exporter。线上默认保持 ``otlp``。
        self.trace_exporter: str = os.getenv("BKAI_AGENT_TRACE_EXPORTER", "otlp").strip().lower()

        # ===== 性能优化配置 =====
        # 通用、输入、输出上限均由 aidev_agent.config 统一读取和覆盖。
        self.max_attribute_length = max(1, int(agent_settings.BKAI_AGENT_MAX_ATTRIBUTE_LENGTH))
        self.max_input_attribute_length = max(1, int(agent_settings.BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH))
        self.max_output_attribute_length = max(1, int(agent_settings.BKAI_AGENT_MAX_OUTPUT_ATTRIBUTE_LENGTH))

    @property
    def span_attribute_length_limit(self) -> int:
        """返回 SDK 全局安全边界，分类属性仍由写入逻辑按各自配置收紧。"""
        return max(
            self.max_attribute_length,
            self.max_input_attribute_length,
            self.max_output_attribute_length,
        )

    def __repr__(self) -> str:
        endpoints_summary = f"{len(self.otel_endpoints)} endpoint(s)"
        if self.otel_endpoints:
            endpoints_summary += f": {', '.join(ep['url'] for ep in self.otel_endpoints)}"

        return (
            f"OTelConfig("
            f"enabled={self.enabled}, "
            f"service_name={self.service_name}, "
            f"otel_endpoints={endpoints_summary}, "
            f"enable_traces={self.enable_traces}, "
            f"trace_exporter={self.trace_exporter})"
        )
