# -*- coding: utf-8 -*-

from aidev_agent.api.utils import get_endpoint
from aidev_agent.config import settings

# 网关接口
BKAIDEV_URL = settings.BK_AIDEV_APIGW_ENDPOINT or get_endpoint(settings.BK_AIDEV_GATEWAY_NAME, settings.BK_APIGW_STAGE)


# SSM服务相关配置
# 根据运行模式自动选择SSM端点
def get_ssm_url() -> str:
    """获取SSM服务URL"""
    if settings.BK_SSM_ENDPOINT:
        return settings.BK_SSM_ENDPOINT

    # 根据运行环境自动选择
    if hasattr(settings, "RUN_MODE"):
        if settings.RUN_MODE == "PRODUCT":
            return settings.BK_SSM_SG_ENDPOINT or ""
        else:
            return settings.BK_SSM_BKOP_ENDPOINT or ""

    # 默认使用BKOP环境
    return settings.BK_SSM_BKOP_ENDPOINT or ""


SSM_URL = get_ssm_url()
