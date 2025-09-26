# -*- coding: utf-8 -*-

from aidev_agent.api.utils import get_endpoint
from aidev_agent.config import settings

# 网关接口
BKAIDEV_URL = settings.BK_AIDEV_APIGW_ENDPOINT or get_endpoint(settings.BK_AIDEV_GATEWAY_NAME, settings.BK_APIGW_STAGE)


# SSM服务相关配置（默认值仅供本地开发使用，请在生产环境中配置正确的地址）
SSM_URL = settings.BK_SSM_ENDPOINT or "https://example.com"
