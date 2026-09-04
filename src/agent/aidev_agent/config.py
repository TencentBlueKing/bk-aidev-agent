# -*- coding: utf-8 -*-
import enum
import os
from typing import Optional

import environs


class SettingEnvVariables(enum.Enum):
    APP_CODE = "BKPAAS_APP_ID"
    SECRET_KEY = "BKPAAS_APP_SECRET"

    # apigateway
    BK_API_URL_TMPL = "BK_API_URL_TMPL"
    BK_APIGW_STAGE = "BK_APIGW_STAGE"
    BK_AIDEV_GATEWAY_NAME = "AIDEV_GATEWAY_NAME"
    BK_AIDEV_APIGW_ENDPOINT = "BK_AIDEV_APIGW_ENDPOINT"


class Settings(object):
    _instance: Optional["Settings"] = None

    def __init__(
        self,
        settings=None,  # type: Any
    ):
        self._settings = settings
        self._defaults = {}  # type: Dict[str, Any]
        self._resolved = {}  # type: Dict[str, Any]

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = Settings()
        return cls._instance

    def __getattr__(self, key: str) -> any:
        """
        get settings from self
        """
        return self.get(key)

    def get(
        self,
        key,  # type: str
        default=None,  # type: Any
    ):
        # type: (...) -> Any
        """
        Returns the specified value, if not found, return to the default value
        """

        # If the key has been hold in the cache, return it directly
        if key in self._resolved:
            return self._resolved[key]

        if self._settings and hasattr(self._settings, key):
            value = self._resolved[key] = getattr(self._settings, key)
            return value

        if key in self._defaults:
            value = self._resolved[key] = self._defaults[key]
            return value

        if getattr(SettingEnvVariables, key, None):
            value = os.environ.get(key)
            return value if value else default

        return default

    def set(self, key, value):
        """
        Set the value of the key
        """

        self._resolved[key] = value

    def set_settings(self, settings_):
        self._settings = settings_

    def set_defaults(self, defaults_):
        """
        Set the default value of the key
        """
        if defaults_:
            self._defaults.update(defaults_)

    def reset(self):
        """
        Reset the resolved cache
        """

        self._resolved.clear()


settings = Settings.get_instance()


def update_django_settings(django_settings=None):
    """
    将当前的 settings 配置 更新到 Django 的 settings
    """
    if django_settings is None:
        from django.conf import settings as django_settings  # noqa
    for attr, value in settings._resolved.items():
        setattr(django_settings, attr, value)


env = environs.Env()
env.read_env()


existed_keys = list(locals().keys())
existed_keys.append("existed_keys")


# begin: 配置
ENABLE_SIMILARITY_MODEL = env.bool("ENABLE_SIMILARITY_MODEL", False)
BKAIDEV_FINE_GRAINED_SCORE_TYPE = (
    env.str("BKAIDEV_FINE_GRAINED_SCORE_TYPE", "LLM") if not ENABLE_SIMILARITY_MODEL else "EXCLUSIVE_SIMILARITY_MODEL"
)
BKAIDEV_TOP_K = env.int("BKAIDEV_TOP_K", 10)
BKAIDEV_KNOWLEDGE_RESOURCE_REJECT_THRESHOLD = env.str("BKAIDEV_KNOWLEDGE_RESOURCE_REJECT_THRESHOLD", "0.0001,0.1")
LLM_GW_ENDPOINT = env.str("LLM_GW_ENDPOINT", "") or env.str("LLM_GATEWAY_URL", "")
APP_CODE = env.str("BK_AIDEV_AGENT_APP_CODE", "") or env.str("BKPAAS_APP_ID", "") or env.str("APP_ID", "")
SECRET_KEY = env.str("BK_AIDEV_AGENT_APP_SECRET", "") or env.str("BKPAAS_APP_SECRET", "") or env.str("APP_TOKEN", "")
BK_AIDEV_ENGINE_REGION = env.str("BK_AIDEV_ENGINE_REGION", "") or env.str("BKPAAS_ENGINE_REGION", "default")
RUN_VER = "ieod" if BK_AIDEV_ENGINE_REGION == "ieod" else "open"
BKPAAS_ENVIRONMENT = env.str("BKPAAS_ENVIRONMENT", "dev")
BK_AIDEV_GATEWAY_NAME = env.str("AIDEV_GATEWAY_NAME", "bkaidev")
BK_AIDEV_APIGW_ENDPOINT = env.str("BK_AIDEV_APIGW_ENDPOINT", "")
BK_APIGW_STAGE = env.str("BK_APIGW_STAGE", "") or env.str("BKAIDEV_RESOURCE_STAGE", "prod")
BKAI_MCP_TIMEOUT = env.int("BKAI_MCP_TIMEOUT", 300)
TOOL_CALL_TIMEOUT = env.int("TOOL_CALL_TIMEOUT", 60)
TOOL_RESULT_LIMIT_THRD = env.int("TOOL_RESULT_LIMIT_THRD", 100000)
MAX_TOKENS = env.int("MAX_TOKENS", None)
REQUEST_API_TIMEOUT = env.int("REQUEST_API_TIMEOUT", 30)
BKAI_TOKEN_CHECK_TIMEOUT = env.int("BKAI_TOKEN_CHECK_TIMEOUT", 3)
MAX_TOOL_OUTPUT_LEN = env.int("MAX_TOOL_OUTPUT_LEN", 5000)
MAX_CACHE_LENGTH = env.int("MAX_CACHE_LENGTH", 50)

# Flow Agent 轮询配置
FLOW_AGENT_POLL_INTERVAL = env.float("FLOW_AGENT_POLL_INTERVAL", 0.5)  # 轮询间隔（秒）
FLOW_AGENT_POLL_TIMEOUT = env.float("FLOW_AGENT_POLL_TIMEOUT", 600.0)  # 轮询超时时间（秒）

# Sandbox 相关配置
SBX_PAAS_NOT_READY_MAX_RETRIES = env.int("SBX_PAAS_NOT_READY_MAX_RETRIES", 5)
SBX_PAAS_NOT_READY_SLEEP_SECONDS = env.int("SBX_PAAS_NOT_READY_SLEEP_SECONDS", 2)
SBX_SENSITIVE_VALUES: list[str] = [v.strip() for v in env.str("SBX_SENSITIVE_VALUES", "").split(",") if v.strip()]

# 沙箱延迟销毁与会话级复用配置
BKAI_RUNTIME_SANDBOX_IDLE_TTL = env.int("BKAI_RUNTIME_SANDBOX_IDLE_TTL", 300)
BKAI_RUNTIME_SANDBOX_SWEEP_INTERVAL = env.int("BKAI_RUNTIME_SANDBOX_SWEEP_INTERVAL", 60)
# 超级过期记录 GC 阈值（秒）：超过该值的共享存储记录由 sweep 末尾 delete_expired 直接删除
# （其远端沙箱早已被平台 TTL 回收，不再做二阶段销毁）。
BKAI_RUNTIME_SANDBOX_RECORD_MAX_AGE = env.int("BKAI_RUNTIME_SANDBOX_RECORD_MAX_AGE", 3 * 24 * 3600)
# 功能开关：启用延迟销毁 RuntimeBackendResolver（RuntimeBackendDeferManager 装配 + 会话级复用）
# 关闭时 resolver 为纯路由，release 立即销毁。原 RUNTIME_SANDBOX_REUSE_ENABLED 已由本开关取代
BKAI_RUNTIME_SANDBOX_DEFERRED_DESTROY_ENABLED = env.bool("BKAI_RUNTIME_SANDBOX_DEFERRED_DESTROY_ENABLED", True)

# SSM相关配置
BK_SSM_ENDPOINT = env.str("BK_SSM_ENDPOINT", "https://bkssm.service.consul")  # noqa

# BkAI 工具开关配置
BKAI_TOOL_A2A_ENABLED = env.bool("BKAI_TOOL_A2A_ENABLED", True)
BKAI_TOOL_TEAM_ENABLED = env.bool("BKAI_TOOL_TEAM_ENABLED", True)
BKAI_TOOL_TASK_ENABLED = env.bool("BKAI_TOOL_TASK_ENABLED", True)
# BKAI 子智能体配置
BKAI_A2A_SESSION_TEMPORARY = env.bool("BKAI_A2A_SESSION_TEMPORARY", False)
# LLM 重试策略: "sdk" 由 aidev 自主控制重试, "llm_gw" 由模型网关 Retry-After 头控制重试
LLM_RETRY_STRATEGY = env.str("LLM_RETRY_STRATEGY", "llm_gw")
# 质量判断模型配置（用于 quality_gate 判断模型是否完成任务）
BKAI_FAST_LLM = env.str("BKAI_FAST_LLM", None)
# 是否启用任务完成度评估（None 表示不覆盖平台配置）
BKAI_ENABLE_JUDGE_RESPONSE = env.bool("BKAI_ENABLE_JUDGE_RESPONSE", None)

# Agent 事件配置
BKAI_EVENT_DATABASE_ENABLED = env.bool("BKAI_EVENT_DATABASE_ENABLED", True)

# Agent 指标与异步任务配置
# None 表示未通过环境变量显式覆盖，允许平台下发的 otel_info.metrics.enabled 生效。
BKAI_AGENT_ENABLE_METRICS = env.bool("BKAI_AGENT_ENABLE_METRICS", None)
BKAI_AGENT_MAX_ATTRIBUTE_LENGTH = max(1, env.int("BKAI_AGENT_MAX_ATTRIBUTE_LENGTH", 10000))
# 与 LLM Gateway 的 LLM 输入、输出 Trace 属性上限保持一致。
BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH = max(1, env.int("BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH", 80 * 1024))
BKAI_AGENT_MAX_OUTPUT_ATTRIBUTE_LENGTH = max(1, env.int("BKAI_AGENT_MAX_OUTPUT_ATTRIBUTE_LENGTH", 20 * 1024))
BKAI_AGENT_METRICS_EXPORT_INTERVAL_MILLIS = env.int("BKAI_AGENT_METRICS_EXPORT_INTERVAL_MILLIS", None)
if BKAI_AGENT_METRICS_EXPORT_INTERVAL_MILLIS is not None:
    BKAI_AGENT_METRICS_EXPORT_INTERVAL_MILLIS = max(10_000, BKAI_AGENT_METRICS_EXPORT_INTERVAL_MILLIS)
BKAI_AGENT_METRICS_PUSH_MODE = env.str("BKAI_AGENT_METRICS_PUSH_MODE", None)
if BKAI_AGENT_METRICS_PUSH_MODE is not None:
    BKAI_AGENT_METRICS_PUSH_MODE = BKAI_AGENT_METRICS_PUSH_MODE.strip().lower()
BKAI_AGENT_METRICS_DATA_ID = env.str("BKAI_AGENT_METRICS_DATA_ID", "")
BKAI_AGENT_METRICS_TOKEN = env.str("BKAI_AGENT_METRICS_TOKEN", "")
BKAI_AGENT_METRICS_HOST = env.str("BKAI_AGENT_METRICS_HOST", "") or env.str("PROXY_IP", "")
BKAI_AGENT_METRICS_TARGET = env.str("BKAI_AGENT_METRICS_TARGET", "")
BKAI_AGENT_METRICS_TASK_TTL_SECONDS = env.int("BKAI_AGENT_METRICS_TASK_TTL_SECONDS", None)
if BKAI_AGENT_METRICS_TASK_TTL_SECONDS is not None:
    BKAI_AGENT_METRICS_TASK_TTL_SECONDS = max(1, BKAI_AGENT_METRICS_TASK_TTL_SECONDS)
BKAI_AGENT_QUEUE_METRIC = "bkai_agent_metric"
BKAI_AGENT_TASK = "bkai_agent_task"
# end: 配置


settings.set_defaults({k: v for k, v in locals().items() if k not in existed_keys})
