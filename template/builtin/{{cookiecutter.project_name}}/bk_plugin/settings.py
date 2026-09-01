# -*- coding: utf-8 -*-

import os
import sys
from warnings import warn

from blueapps.patch.settings_paas_services import CACHES, INSTALLED_APPS  # noqa

DEFAULT_CACHE_TIMEOUT = 60

CACHES["default"] = {
    "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
    "LOCATION": "/tmp/django_cache",
}

# SaaS运行版本
RUN_VER = "ieod" if os.environ.get("BKPAAS_ENGINE_REGION", "default") == "ieod" else "open"

# 智能体插件版本
VERSION_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "VERSION")

# 需要合并的配置
SETTINGS_FOR_MERGE = ["INSTALLED_APPS", "MIDDLEWARE", "AUTHENTICATION_BACKENDS"]
SETTINGS_FOR_UPDATE = ["DATABASES"]


def load_settings(module_path: str, raise_exception: bool = True):
    try:
        module = __import__(module_path, globals(), locals(), ["*"])
    except ImportError as err:
        msg = "Could not import config '{}' (Is it on sys.path?): {}".format(module_path, err)
        if raise_exception:
            raise ImportError(msg)
        warn(msg)
        return
    for setting in dir(module):
        if setting == setting.upper():
            if setting in SETTINGS_FOR_MERGE and setting in globals():
                # mix global setting and module setting
                globals()[setting] = (
                    *globals()[setting],
                    *(_s for _s in getattr(module, setting) if _s not in globals()[setting]),
                )
            elif setting in SETTINGS_FOR_UPDATE and setting in globals():
                globals()[setting].update(getattr(module, setting))
            else:
                globals()[setting] = getattr(module, setting)


# 加载自定义模块
load_settings("aidev_bkplugin.settings")  # 蓝鲸插件配置
load_settings("aidev_ai_blueking.settings")  # 小鲸配置
load_settings("aidev_wxbot.settings")  # 企微机器人配置

# 插件配置
AIDEV_AGENT = os.environ.get("AIDEV_AGENT", "bk_plugin.extend.agent.CommonQAAgentExtend")
AIDEV_RESOURCE_MANAGER = os.environ.get(
    "AIDEV_RESOURCE_MANAGER",
    "bk_plugin.extend.resource_manager.CustomAgentResourceManager",
)

REST_FRAMEWORK = {
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
    "EXCEPTION_HANDLER": "aidev_bkplugin.packages.drf.exception.custom_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ("aidev_bkplugin.packages.drf.renderers.APIRenderer",),
}

# 智能体接口授权
BK_APIGW_GRANTED_APPS = os.getenv("BKAPP_APIGW_GRANTED_APPS") or os.getenv("BK_APIGW_GRANTED_APPS")
BK_APIGW_GRANTED_APPS = BK_APIGW_GRANTED_APPS.split(",") if BK_APIGW_GRANTED_APPS else []
BK_APIGW_GRANTED_APPS.append(locals().get("BKPAAS_APP_CODE"))

# 本地开发环境全局放开跨域（仅 dev/development 生效）
if os.getenv("BKPAAS_ENVIRONMENT", "dev").lower() in {"dev", "development"}:
    if "corsheaders" not in INSTALLED_APPS:
        INSTALLED_APPS = (*INSTALLED_APPS, "corsheaders")

    # 避免在 MIDDLEWARE 尚未就绪时覆盖默认中间件链
    middleware = locals().get("MIDDLEWARE")
    if middleware and "corsheaders.middleware.CorsMiddleware" not in middleware:
        MIDDLEWARE = ("corsheaders.middleware.CorsMiddleware", *middleware)

    runtime_module_names = (
        "bk_plugin_runtime.config.dev",
        "bk_plugin_runtime.config.stag",
        "bk_plugin_runtime.config.prod",
    )
    for module_name in runtime_module_names:
        runtime_module = sys.modules.get(module_name)
        if runtime_module is None:
            continue

        runtime_installed_apps = getattr(runtime_module, "INSTALLED_APPS", ())
        if "corsheaders" not in runtime_installed_apps:
            setattr(runtime_module, "INSTALLED_APPS", (*runtime_installed_apps, "corsheaders"))

        runtime_middleware = getattr(runtime_module, "MIDDLEWARE", ())
        if runtime_middleware and "corsheaders.middleware.CorsMiddleware" not in runtime_middleware:
            setattr(runtime_module, "MIDDLEWARE", ("corsheaders.middleware.CorsMiddleware", *runtime_middleware))

    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True

# 自定义应用：在 apps 目录下创建应用，然后在这里加载
# load_settings("apps.demo.settings")


def _is_truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _enable_console_log_for_local_debug():
    """Expose root logger output to stdout in local debug sessions."""
    is_local_env = os.getenv("BKPAAS_ENVIRONMENT", "dev").lower() in {"dev", "development"}
    enabled = _is_truthy(os.getenv("AIDEV_STDOUT_LOG_ENABLED"), default=is_local_env)
    if not enabled:
        return

    level = os.getenv("AIDEV_STDOUT_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO")).upper()
    runtime_module_names = (
        "bk_plugin_runtime.config.dev",
        "bk_plugin_runtime.config.stag",
        "bk_plugin_runtime.config.prod",
    )
    for module_name in runtime_module_names:
        runtime_module = sys.modules.get(module_name)
        if runtime_module is None:
            continue

        logging_config = getattr(runtime_module, "LOGGING", None)
        if not isinstance(logging_config, dict):
            continue

        handlers = logging_config.setdefault("handlers", {})
        formatters = logging_config.setdefault("formatters", {})
        if "verbose" in formatters:
            formatter_name = "verbose"
        elif formatters:
            formatter_name = next(iter(formatters))
        else:
            formatter_name = "simple"
            formatters["simple"] = {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}

        handlers.setdefault(
            "console",
            {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": formatter_name,
            },
        )

        root_logger = logging_config.setdefault("loggers", {}).setdefault("root", {})
        root_handlers = root_logger.setdefault("handlers", [])
        if "console" not in root_handlers:
            root_handlers.append("console")
        root_logger.setdefault("level", level)


_enable_console_log_for_local_debug()


# Local E2E uses a real, isolated SQLite file by default. Production and normal
# template development remain on the runtime-provided database configuration.
if os.getenv("BKPAAS_ENVIRONMENT", "dev").lower() in {"dev", "development"} and os.getenv("E2E_SQLITE_PATH"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ["E2E_SQLITE_PATH"],
        }
    }
