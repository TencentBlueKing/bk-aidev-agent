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

import json
import os
from enum import Enum
from typing import Any, Dict, List

from aidev_bkplugin.services.agent import get_agent_config_info


class ExporterType(Enum):
    """OTEL Exporter 类型"""

    GRPC = "grpc"
    HTTP = "http"


class OTelConfig:
    """OTel 上报配置"""

    def __init__(self):
        # ===== 基础配置 =====
        self.enabled = self._get_env_bool("BKAI_AGENT_OTEL_ENABLED", True)
        self.debug = self._get_env_bool("BKAI_AGENT_OTEL_DEBUG", False)

        # ===== OTEL Endpoint 配置 =====
        # 使用BKPAAS_APP_CODE作为 service_name
        self.service_name = os.getenv("BKPAAS_APP_ID", "") or os.getenv("BKPAAS_APP_CODE", "aidev-agent")

        # ===== OTel Endpoint 地址(支持多个) =====
        self.otel_endpoints = self.get_endpoints()

        # ===== 功能开关 =====
        self.enable_traces = self._get_env_bool("BKAI_AGENT_ENABLE_TRACES", True)
        self.enable_metrics = self._get_env_bool("BKAI_AGENT_ENABLE_METRICS", False)
        self.enable_logs = self._get_env_bool("BKAI_AGENT_ENABLE_LOGS", False)

        # ===== 性能优化配置 =====
        # 最大字符串长度限制
        self.max_attribute_length = int(os.getenv("BKAI_AGENT_MAX_ATTRIBUTE_LENGTH", "10000"))

    def get_otel_info(self) -> tuple[str | None, str | None]:
        try:
            agent_info = get_agent_config_info()
            otel_info = agent_info.get("otel_info")
            return otel_info.get("otel_url"), otel_info.get("otel_token")
        except Exception:
            # 无法获取公共上报地址
            return None, None

    def get_endpoints(self) -> List[Dict[str, Any]]:
        """
        获取所有端点配置

        优先级:
        1. BKAI_AGENT_OTEL_ENDPOINTS (支持多地址)
        2. BKAI_AGENT_OTEL_ENDPOINT + BKAI_AGENT_OTEL_TOKEN (单地址)
        3. OTEL_GRPC_URL + OTEL_BK_DATA_TOKEN (单地址)

        Returns:
            List[Dict[str, Any]]: 端点配置列表
        """
        urls = []

        # 1. 从 BKAI_AGENT_OTEL_ENDPOINTS 解析多地址
        endpoints_str = os.getenv("BKAI_AGENT_OTEL_ENDPOINTS", "")
        if endpoints_str:
            urls.extend(self._parse_endpoints(endpoints_str))

        # 2. 从 BKAI_AGENT_OTEL_ENDPOINT 获取单地址
        endpoint, token = self.get_otel_info()
        if endpoint and token:
            default_exporter_type = ExporterType(os.getenv("BKAI_AGENT_OTEL_EXPORTER_TYPE", "grpc").lower())
            urls.append(
                {
                    "url": endpoint,
                    "token": token,
                    "exporter_type": default_exporter_type,
                    "batch_max_queue_size": int(os.getenv("BKAI_AGENT_BATCH_MAX_QUEUE_SIZE", "2048")),
                    "batch_schedule_delay_millis": int(os.getenv("BKAI_AGENT_BATCH_SCHEDULE_DELAY_MILLIS", "5000")),
                    "batch_export_timeout_millis": int(os.getenv("BKAI_AGENT_BATCH_EXPORT_TIMEOUT_MILLIS", "30000")),
                    "batch_max_export_batch_size": int(os.getenv("BKAI_AGENT_BATCH_MAX_EXPORT_BATCH_SIZE", "512")),
                }
            )

        # 3. 从 OTEL_GRPC_URL 获取单地址
        otel_enable = self._get_env_bool("BKAI_AGENT_APM_OTEL_ENABLED", False)
        otel_grpc_url = os.getenv("OTEL_GRPC_URL", "")
        otel_bk_data_token = os.getenv("OTEL_BK_DATA_TOKEN", "")
        if otel_enable and otel_grpc_url and otel_bk_data_token:
            urls.append(
                {
                    "url": otel_grpc_url,
                    "token": otel_bk_data_token,
                    "exporter_type": ExporterType.GRPC,  # OTEL_GRPC_URL 固定使用 GRPC
                    "batch_max_queue_size": int(os.getenv("BKAI_AGENT_BATCH_MAX_QUEUE_SIZE", "2048")),
                    "batch_schedule_delay_millis": int(os.getenv("BKAI_AGENT_BATCH_SCHEDULE_DELAY_MILLIS", "5000")),
                    "batch_export_timeout_millis": int(os.getenv("BKAI_AGENT_BATCH_EXPORT_TIMEOUT_MILLIS", "30000")),
                    "batch_max_export_batch_size": int(os.getenv("BKAI_AGENT_BATCH_MAX_EXPORT_BATCH_SIZE", "512")),
                }
            )
        return urls

    def _parse_endpoints(self, endpoints_str: str) -> List[Dict[str, Any]]:
        """
        解析多个 OTEL Endpoint 配置

        支持三种格式:
        1. 单个URL: "http://localhost:4317"
        2. 多个URL(逗号分隔): "http://host1:4317,http://host2:4317"
        3. JSON格式(支持独立配置):
           '[{"url": "http://host1:4317", "token": "xxx", "exporter_type": "grpc"},
             {"url": "http://host2:4318", "token": "yyy", "exporter_type": "http"}]'

        Returns:
            List[Dict[str, Any]]: 端点配置列表,每个配置包含:
                - url: 端点地址
                - token: 认证 token (可选)
                - exporter_type: 导出器类型 (grpc/http,默认继承全局配置)
                - batch_max_queue_size: 批处理队列大小 (可选,默认继承全局配置)
                - batch_schedule_delay_millis: 批处理调度延迟 (可选)
                - batch_export_timeout_millis: 批处理导出超时 (可选)
                - batch_max_export_batch_size: 批处理最大批量大小 (可选)
        """
        if not endpoints_str or endpoints_str.strip() == "":
            return []

        endpoints_str = endpoints_str.strip()

        # 尝试解析为 JSON
        if endpoints_str.startswith("["):
            try:
                parsed = json.loads(endpoints_str)
                if not isinstance(parsed, list):
                    raise ValueError("JSON format must be a list of endpoint configs")

                result = []
                for idx, endpoint in enumerate(parsed):
                    if not isinstance(endpoint, dict):
                        raise ValueError(f"Endpoint {idx} must be a dict")
                    if "url" not in endpoint:
                        raise ValueError(f"Endpoint {idx} missing 'url' field")

                    # 规范化配置
                    config = {
                        "url": endpoint["url"],
                        "token": endpoint.get("token", os.getenv("BKAI_AGENT_OTEL_TOKEN", "")),
                        "exporter_type": ExporterType(endpoint.get("exporter_type", "grpc").lower()),
                        # 批处理配置(优先使用端点配置,否则使用全局环境变量)
                        "batch_max_queue_size": endpoint.get(
                            "batch_max_queue_size", int(os.getenv("BKAI_AGENT_BATCH_MAX_QUEUE_SIZE", "2048"))
                        ),
                        "batch_schedule_delay_millis": endpoint.get(
                            "batch_schedule_delay_millis",
                            int(os.getenv("BKAI_AGENT_BATCH_SCHEDULE_DELAY_MILLIS", "5000")),
                        ),
                        "batch_export_timeout_millis": endpoint.get(
                            "batch_export_timeout_millis",
                            int(os.getenv("BKAI_AGENT_BATCH_EXPORT_TIMEOUT_MILLIS", "30000")),
                        ),
                        "batch_max_export_batch_size": endpoint.get(
                            "batch_max_export_batch_size",
                            int(os.getenv("BKAI_AGENT_BATCH_MAX_EXPORT_BATCH_SIZE", "512")),
                        ),
                    }
                    result.append(config)

                return result
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON format for BKAI_AGENT_OTEL_ENDPOINTS: {e}")

        # 简单格式: 单个URL 或 逗号分隔的多个URL
        urls = [url.strip() for url in endpoints_str.split(",") if url.strip()]
        # 使用全局默认配置
        default_token = os.getenv("BKAI_AGENT_OTEL_TOKEN", "")
        default_exporter_type = ExporterType(os.getenv("BKAI_AGENT_OTEL_EXPORTER_TYPE", "grpc").lower())

        return [
            {
                "url": url,
                "token": default_token,
                "exporter_type": default_exporter_type,
                "batch_max_queue_size": int(os.getenv("BKAI_AGENT_BATCH_MAX_QUEUE_SIZE", "2048")),
                "batch_schedule_delay_millis": int(os.getenv("BKAI_AGENT_BATCH_SCHEDULE_DELAY_MILLIS", "5000")),
                "batch_export_timeout_millis": int(os.getenv("BKAI_AGENT_BATCH_EXPORT_TIMEOUT_MILLIS", "30000")),
                "batch_max_export_batch_size": int(os.getenv("BKAI_AGENT_BATCH_MAX_EXPORT_BATCH_SIZE", "512")),
            }
            for url in urls
        ]

    @staticmethod
    def _get_env_bool(key: str, default: bool) -> bool:
        """从环境变量读取布尔值"""
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes")

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
