#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default settings for aidev_wxbot Django app.
These settings can be overridden in the main Django project's settings.
"""

import os

# aidev_wxbot app specific settings
BK_APIGW_MANAGER_URL_TMPL = os.getenv("BK_APIGW_MANAGER_URL_TMPL")
BKPAAS_BK_PLUGIN_APIGW_NAME = os.getenv("BKPAAS_BK_PLUGIN_APIGW_NAME", "")
BKPAAS_APP_SECRET = os.getenv("BKPAAS_APP_SECRET")
BKPAAS_APP_CODE = os.getenv("BKPAAS_APP_ID") or os.getenv("BKPAAS_APP_CODE")

# AIDev openapi endpoint
AIDEV_GATEWAY_NAME= os.getenv("AIDEV_GATEWAY_NAME", "bk-aidev")
BK_APIGW_STAGE = os.getenv("BK_APIGW_STAGE", "prod")

WXAIBOT_TOKEN = os.getenv("BKAPP_WXAIBOT_TOKEN")
WXAIBOT_ENCODING_AES_KEY = os.getenv("BKAPP_WXAIBOT_ENCODING_AES_KEY")
WAXIBOT_NAME = os.getenv("BKAPP_WAXIBOT_NAME", "")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")

IS_INDEPENDENT_BOT = os.getenv("IS_INDEPENDENT_BOT", "false").lower() == 'true'
MAX_MESSAGE_TIME = int(os.getenv("BKAPP_WAXIBOT_MAX_MESSAGE_TIME", 300))
# Default app configuration that can be added to main project settings
INSTALLED_APPS = [
    'rest_framework',
    'aidev_wxbot',
]
