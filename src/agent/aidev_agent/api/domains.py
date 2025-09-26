# -*- coding: utf-8 -*-

from aidev_agent.api.utils import get_endpoint
from aidev_agent.config import settings

# 网关接口
BKAIDEV_URL = settings.BK_AIDEV_APIGW_ENDPOINT or get_endpoint(settings.BK_AIDEV_GATEWAY_NAME, settings.BK_APIGW_STAGE)


# SSM服务相关配置
SSM_URL = settings.BK_SSM_ENDPOINT
