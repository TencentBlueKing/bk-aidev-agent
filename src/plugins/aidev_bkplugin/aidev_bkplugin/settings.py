# -*- coding: utf-8 -*-

import os

# 应用模块
INSTALLED_APPS = ("aidev_bkplugin",)

# 智能体
AIDEV_AGENT = os.environ.get("AIDEV_AGENT", "aidev_agent.services.common_agent.CommonQAAgent")
# 自定义 ResourceManager 实现（继承 ``AgentResourceManager``），通过
# ``resource_manager.replace_defaults(...)`` 注入到全局工厂；为空则使用 SDK 默认的
# ``AgentResourceManager``。
AIDEV_RESOURCE_MANAGER = os.environ.get("AIDEV_RESOURCE_MANAGER", "")
AIDEV_AGENT_MAX_WORKERS = int(os.environ.get("BKAPP_AIDEV_AGENT_MAX_WORKERS", 16))
AIDEV_AGENT_MAX_PENDING = int(os.environ.get("BKAPP_AIDEV_AGENT_MAX_PENDING", 32))

# 客服渠道
CHAT_GROUP_ENABLED = os.environ.get("CHAT_GROUP_ENABLED") == "1"
CHAT_GROUP_STAFF = os.environ.get("CHAT_GROUP_STAFF")
CHAT_GROUP_STAFF = [i.strip() for i in CHAT_GROUP_STAFF.split(",")] if CHAT_GROUP_STAFF else []
CHAT_GROUP_TYPE = os.environ.get("CHAT_GROUP_TYPE", "qyweixin_chat_group")


############### APM
ENABLE_OTEL_TRACE = os.getenv("BKAPP_ENABLE_OTEL_TRACE", "1") == "1"
BK_APP_OTEL_INSTRUMENT_DB_API = os.getenv("BKAPP_OTEL_INSTRUMENT_DB_API", "1") == "1"

# OpenTelemetry 是可选 extras，未安装时不注册任何额外 instrumentor。
# 安装方式：pip install aidev-bkplugin[opentelemetry]
BK_APP_OTEL_ADDTIONAL_INSTRUMENTORS: list = []
try:
    from opentelemetry.instrumentation.langchain import LangchainInstrumentor

    BK_APP_OTEL_ADDTIONAL_INSTRUMENTORS = [LangchainInstrumentor()]
except ImportError:
    pass

# SaaS运行版本
RUN_VER = "ieod" if os.environ.get("BKPAAS_ENGINE_REGION", "default") == "ieod" else "open"

# OAuth 认证配置
BKAUTH_BACKEND_TYPE = "bk_ticket" if RUN_VER == "ieod" else "bk_token"

# 仅社区版需要配置，其它版本已由开发框架处理
if BKAUTH_BACKEND_TYPE == 'bk_token':
    OAUTH_COOKIES_PARAMS = {"bk_token": "bk_token", "bk_uid": "bk_uid"}

    os.environ['OAUTH_API_URL'] = (
        os.getenv('BKAPP_OAUTH_API_URL') or
        os.getenv('BKPAAS_SSM_API_URL') or
        'http://bkssm.service.consul'
    )

    # OAuth 临近过期时间：生效期在 1 小时内则自动刷新 token
    EXPIRES_SECONDS = 60 * 60
