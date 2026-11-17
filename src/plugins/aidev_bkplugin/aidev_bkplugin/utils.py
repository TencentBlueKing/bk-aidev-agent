import os
from logging import getLogger

logger = getLogger(__name__)


def set_user_access_token(request):
    """用登录态换用户 access_token，并 bind 到 craw 请求上下文。

    返回归一后的 token 字符串（换票失败则为空串）。不把 token 写入日志。
    """
    token = ""
    if request is None:
        try:
            from aidev_agent.packages.craw.mcp_identity import bind_user_access_token
        except ImportError:
            return ""
        bind_user_access_token("")
        return ""
    try:
        import bkoauth

        issued = bkoauth.get_access_token(request)
        token = getattr(issued, "access_token", "") or ""
    except Exception as err:
        logger.warning("failed to get user access_token via bkoauth: %s", err)
    try:
        from aidev_agent.packages.craw.mcp_identity import bind_user_access_token, normalize_access_token
    except ImportError:
        return token
    token = normalize_access_token(token)
    bind_user_access_token(token)
    return token


def is_local_dev():
    return os.getenv("BKPAAS_ENVIRONMENT", "dev").lower() in {"dev", "development"}
