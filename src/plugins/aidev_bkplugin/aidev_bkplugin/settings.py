# -*- coding: utf-8 -*-

import os
from blueapps.patch.settings_paas_services import STATICFILES_DIRS  # noqa

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

CUR_DIR = os.path.dirname(__file__)
STATIC_TEMPLATE_ROOT = os.path.join(CUR_DIR, "dist")
STATICFILES_DIRS += [os.path.join(STATIC_TEMPLATE_ROOT, "static")]
