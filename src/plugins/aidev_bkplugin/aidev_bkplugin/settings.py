# -*- coding: utf-8 -*-

import os
from opentelemetry.instrumentation.langchain import LangchainInstrumentor

# 应用模块
INSTALLED_APPS = ("aidev_bkplugin",)

# 智能体
DEFAULT_NAME = "default"
DEFAULT_AGENT = os.environ.get("DEFAULT_AGENT", "aidev_agent.core.extend.agent.qa.CommonQAAgent")
DEFAULT_CONFIG_MANAGER = os.environ.get("DEFAULT_CONFIG_MANAGER", "aidev_agent.services.config_manager.AgentConfigManager")

# 客服渠道
CHAT_GROUP_ENABLED = os.environ.get("CHAT_GROUP_ENABLED") == "1"
CHAT_GROUP_STAFF = os.environ.get("CHAT_GROUP_STAFF")
CHAT_GROUP_STAFF = [i.strip() for i in CHAT_GROUP_STAFF.split(",")] if CHAT_GROUP_STAFF else []
CHAT_GROUP_TYPE = os.environ.get("CHAT_GROUP_TYPE", "qyweixin_chat_group")


############### APM
ENABLE_OTEL_TRACE = os.getenv("BKAPP_ENABLE_OTEL_TRACE", "1") == "1"
BK_APP_OTEL_INSTRUMENT_DB_API = os.getenv("BKAPP_OTEL_INSTRUMENT_DB_API", "1") == "1"

BK_APP_OTEL_ADDTIONAL_INSTRUMENTORS = [
    LangchainInstrumentor(),
]

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
