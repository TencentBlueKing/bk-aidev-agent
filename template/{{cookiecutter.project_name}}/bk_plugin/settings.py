from warnings import warn

from blueapps.patch.settings_paas_services import CACHES, INSTALLED_APPS  # noqa

DEFAULT_CACHE_TIMEOUT = 60

CACHES["default"] = {
    "BACKEND": "django.core.cache.backends.db.DatabaseCache",
    "LOCATION": "my_cache_table",
}

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
load_settings("aidev_bkplugin.settings")  # 智能体配置
load_settings("aidev_ai_blueking.settings")  # 小鲸配置
load_settings("aidev_wxbot.settings")  # 企微机器人配置
