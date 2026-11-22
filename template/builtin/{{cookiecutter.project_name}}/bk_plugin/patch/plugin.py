# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - PaaS平台 (BlueKing - PaaS System) available.
Copyright (C) 2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import os

import pymysql


def _configure_session_queue_url():
    """在插件运行时加载 SDK 前，将平台下发的 Base64 地址还原为 Redis URL。"""
    if os.getenv("MESSAGE_HANDLER_TYPE", "").strip().lower() not in {"", "auto", "redis"}:
        return
    value = os.getenv("MESSAGE_REDIS_URL", "")
    schemes = ("redis://", "rediss://", "unix://")
    if not value or value.startswith(schemes):
        return
    try:
        url = base64.b64decode(value, validate=True).decode("utf-8")
    except ValueError:
        raise ValueError("Invalid MESSAGE_REDIS_URL: expected a Redis URL or its Base64 encoding") from None
    if not url.startswith(schemes) or "\x00" in url:
        raise ValueError("Invalid Redis URL in Base64-encoded MESSAGE_REDIS_URL")
    os.environ["MESSAGE_REDIS_URL"] = url


_configure_session_queue_url()
pymysql.install_as_MySQLdb()

# URL 配置模块

# V3判断环境的环境变量为BKPAAS_ENVIRONMENT
if "BKPAAS_ENVIRONMENT" in os.environ:
    ENVIRONMENT = os.getenv("BKPAAS_ENVIRONMENT", "dev")
# V2判断环境的环境变量为BK_ENV
else:
    PAAS_V2_ENVIRONMENT = os.environ.get("BK_ENV", "development")
    ENVIRONMENT = {
        "development": "dev",
        "testing": "stag",
        "production": "prod",
    }.get(PAAS_V2_ENVIRONMENT)
DJANGO_CONF_MODULE = "bk_plugin_runtime.config.{env}".format(env=ENVIRONMENT)

try:
    _module = __import__(DJANGO_CONF_MODULE, globals(), locals(), ["*"])
except ImportError as e:
    raise ImportError("Could not import config '%s' (Is it on sys.path?): %s" % (DJANGO_CONF_MODULE, e))

for _setting in dir(_module):
    if _setting == _setting.upper():
        locals()[_setting] = getattr(_module, _setting)

# 日志
if locals().get("LOGGING"):
    locals()["LOGGING"]["loggers"]["bkapi_client_core"] = {"handlers": ["root"], "level": "DEBUG", "propagate": True}

ROOT_URLCONF = "bk_plugin.patch.urls"
