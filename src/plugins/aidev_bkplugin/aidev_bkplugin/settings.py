# -*- coding: utf-8 -*-

import os

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
