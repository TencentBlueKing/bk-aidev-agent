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
import dataclasses
import json
import logging
import os
import traceback
from enum import Enum
from functools import lru_cache
from typing import List, Dict, Any

from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.trace import Span
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ExporterType(Enum):
    """OTEL Exporter 类型"""

    GRPC = "grpc"
    HTTP = "http"


class CallbackFilteredJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, dict):
            if "callbacks" in o:
                del o["callbacks"]
                return o

        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)

        if hasattr(o, "to_json"):
            return o.to_json()

        if isinstance(o, BaseModel) and hasattr(o, "model_dump_json"):
            return o.model_dump_json()

        return super().default(o)


def dont_throw(func):
    """
    A decorator that wraps the passed in function and logs exceptions instead of throwing them.

    @param func: The function to wrap
    @return: The wrapper function
    """
    # Obtain a logger specific to the function's module
    logger = logging.getLogger(func.__module__)

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.debug(
                "OpenLLMetry failed to trace in %s, error: %s",
                func.__name__,
                traceback.format_exc(),
            )

    return wrapper


def _safe_attach_context(span: Span):
    """
    安全地将 span 附加到 context,处理异步场景下的潜在失败

    Args:
        span: 要附加的 Span

    Returns:
        context token 用于后续 detach,失败时返回 None
    """
    try:
        # 使用 context_api.attach 而不是 _RUNTIME_CONTEXT.attach
        # 这样可以确保 context 正确传播到 LangChain 的自动插桩中
        return context_api.attach(trace.set_span_in_context(span))
    except Exception as e:
        logger.warning(f"Context attach failed, span hierarchy may be incorrect: {e}")
        return None


def _safe_detach_context(token):
    """
    安全地分离 context token,不会导致应用崩溃

    此方法实现了一个故障安全的 context 分离,处理异步/并发场景中
    context token 可能失效的所有已知边缘情况

    Args:
        token: context token
    """
    if not token:
        return

    try:
        # 直接使用 runtime context 避免 context_api.detach() 的错误日志
        # context_api 会使用 logger.exception 记录
        # 根据 LangChain 官方的说法，LangChain detach 失败是安全的
        from opentelemetry.context import _RUNTIME_CONTEXT

        _RUNTIME_CONTEXT.detach(token)
    except Exception as e:
        # Context detach 在异步场景下可能失败,这是预期的行为
        # 常见场景:
        # 1. Token 在一个 async task/thread 中创建,在另一个中 detach
        # 2. Context 已经被其他进程 detach
        # 3. Token 由于 context 切换而失效
        # 4. 高并发场景下的竞态条件
        #
        # 这是安全的,因为 span 本身已经正确结束,追踪数据已正确捕获
        logger.debug(f"Context detach failed: {e}")


def _set_span_attribute(span: Span, key: str, value: Any) -> None:
    if value is not None:
        if value != "":
            span.set_attribute(key, value)
        else:
            span.set_attribute(key, "")


def _sanitize_metadata_value(value: Any) -> Any:
    """Convert metadata values to OpenTelemetry-compatible types."""
    if value is None:
        return None
    if isinstance(value, (bool, str, bytes, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [str(_sanitize_metadata_value(v)) for v in value]
    # Convert other types to strings
    return str(value)


def get_env_bool(key: str, default: bool) -> bool:
    """从环境变量读取布尔值"""
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes")


def get_otel_endpoint_by_agent_info() -> tuple[str | None, str | None]:
    try:
        from aidev_bkplugin.services.agent import get_agent_config_info
        agent_info = get_agent_config_info()
        otel_info = agent_info.get("otel_info")
        return otel_info.get("otel_url"), otel_info.get("otel_token")
    except Exception:
        # 无法获取公共上报地址
        return None, None

def get_otel_endpoint_by_json_str( endpoints_str: str) -> List[Dict[str, Any]]:
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


@lru_cache(maxsize=1)
def get_otel_endpoints():
    """
    获取所有端点配置

    优先级:
    1. BKAI_AGENT_OTEL_ENDPOINTS (支持多地址)
    2. BKAI_AGENT_OTEL_ENDPOINT + BKAI_AGENT_OTEL_TOKEN (单地址)
    3. OTEL_GRPC_URL + OTEL_BK_DATA_TOKEN (单地址)

    Returns:
        List[Dict[str, Any]]: 端点配置列表
    """
    endpoints = []
    batch_max_queue_size = int(os.getenv("BKAI_AGENT_BATCH_MAX_QUEUE_SIZE", "2048"))
    batch_schedule_delay_millis = int(os.getenv("BKAI_AGENT_BATCH_SCHEDULE_DELAY_MILLIS", "5000"))
    batch_export_timeout_millis = int(os.getenv("BKAI_AGENT_BATCH_EXPORT_TIMEOUT_MILLIS", "30000"))
    batch_max_export_batch_size = int(os.getenv("BKAI_AGENT_BATCH_MAX_EXPORT_BATCH_SIZE", "512"))
    # 1. 从 BKAI_AGENT_OTEL_ENDPOINTS 解析多地址
    endpoints_str = os.getenv("BKAI_AGENT_OTEL_ENDPOINTS", "")
    if endpoints_str:
        endpoints.extend(get_otel_endpoint_by_json_str(endpoints_str))

    # 2. 从 BKAI_AGENT_OTEL_ENDPOINT 获取单地址
    endpoint, token = get_otel_endpoint_by_agent_info()
    if endpoint and token:
        default_exporter_type = ExporterType(os.getenv("BKAI_AGENT_OTEL_EXPORTER_TYPE", "grpc").lower())
        endpoints.append(
            {
                "url": endpoint,
                "token": token,
                "exporter_type": default_exporter_type,
                "batch_max_queue_size": batch_max_queue_size,
                "batch_schedule_delay_millis": batch_schedule_delay_millis,
                "batch_export_timeout_millis": batch_export_timeout_millis,
                "batch_max_export_batch_size": batch_max_export_batch_size,
            }
        )

    # 3. 从 OTEL_GRPC_URL 获取单地址
    otel_enable = get_env_bool("BKAI_AGENT_APM_OTEL_ENABLED", False)
    otel_grpc_url = os.getenv("OTEL_GRPC_URL", "")
    otel_bk_data_token = os.getenv("OTEL_BK_DATA_TOKEN", "")
    if otel_enable and otel_grpc_url and otel_bk_data_token:
        endpoints.append(
            {
                "url": otel_grpc_url,
                "token": otel_bk_data_token,
                "exporter_type": ExporterType.GRPC,  # OTEL_GRPC_URL 固定使用 GRPC
                "batch_max_queue_size": batch_max_queue_size,
                "batch_schedule_delay_millis": batch_schedule_delay_millis,
                "batch_export_timeout_millis": batch_export_timeout_millis,
                "batch_max_export_batch_size": batch_max_export_batch_size,
            }
        )
    return endpoints
