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
BK_APIGW_MCP_TIMEOUT = env.str("BK_APIGW_MCP_TIMEOUT", "300")
TOOL_CALL_TIMEOUT = env.int("TOOL_CALL_TIMEOUT", 60)
TOOL_RESULT_LIMIT_THRD = env.int("TOOL_RESULT_LIMIT_THRD", 100000)
MAX_TOKENS = env.int("MAX_TOKENS", None)
REQUEST_API_TIMEOUT = env.int("REQUEST_API_TIMEOUT", 30)
MAX_TOOL_OUTPUT_LEN = env.int("MAX_TOOL_OUTPUT_LEN", 5000)
MAX_CACHE_LENGTH = env.int("MAX_CACHE_LENGTH", 50)

# Flow Agent 轮询配置
FLOW_AGENT_POLL_INTERVAL = env.float("FLOW_AGENT_POLL_INTERVAL", 0.5)  # 轮询间隔（秒）
FLOW_AGENT_POLL_TIMEOUT = env.float("FLOW_AGENT_POLL_TIMEOUT", 600.0)  # 轮询超时时间（秒）

# Sandbox 相关配置
SBX_PAAS_NOT_READY_MAX_RETRIES = env.int("SBX_PAAS_NOT_READY_MAX_RETRIES", 5)
SBX_PAAS_NOT_READY_SLEEP_SECONDS = env.int("SBX_PAAS_NOT_READY_SLEEP_SECONDS", 2)
SBX_SENSITIVE_VALUES: list[str] = [v.strip() for v in env.str("SBX_SENSITIVE_VALUES", "").split(",") if v.strip()]

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

# Agent 指标与异步任务配置
# None 表示未通过环境变量显式覆盖，允许平台下发的 otel_info.metrics.enabled 生效。
BKAI_AGENT_ENABLE_METRICS = env.bool("BKAI_AGENT_ENABLE_METRICS", None)
BKAI_AGENT_METRICS_DATA_ID = env.str("BKAI_AGENT_METRICS_DATA_ID", "")
BKAI_AGENT_METRICS_TOKEN = env.str("BKAI_AGENT_METRICS_TOKEN", "")
BKAI_AGENT_METRICS_HOST = env.str("BKAI_AGENT_METRICS_HOST", "") or env.str("PROXY_IP", "")
BKAI_AGENT_METRICS_TARGET = env.str("BKAI_AGENT_METRICS_TARGET", "")
BKAI_AGENT_METRICS_TASK_TTL_SECONDS = max(1, env.int("BKAI_AGENT_METRICS_TASK_TTL_SECONDS", 3600))
BKAI_AGENT_TASK = "bkai_agent_task"
# end: 配置


settings.set_defaults({k: v for k, v in locals().items() if k not in existed_keys})
