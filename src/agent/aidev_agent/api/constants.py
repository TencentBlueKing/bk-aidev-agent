# -*- coding: utf-8 -*-
from aidev_agent.config import settings

APIGW_URL_FORMAT = "{}/{{stage}}".format(settings.BK_API_URL_TMPL)

AUTHORIZATION_HEADER = "X-Bkapi-Authorization"

# 多租户模式下透传给下游网关的租户 ID 请求头
TENANT_HEADER = "X-Bk-Tenant-Id"

# MCP proxy 透传头：声明哪些 header 需由网关透传给后端业务网关（如 X-Bk-Tenant-Id）
MCP_ALLOWED_HEADERS_HEADER = "X-Bkapi-Allowed-Headers"

# 未从 PaaS 取到应用租户时的默认租户（对齐 blueapps 对全租户应用的处理）
DEFAULT_TENANT_ID = "default"

CONCURRENCY_NUMS = 1

PAGE_SIZE = 10
LIMIT = 500
