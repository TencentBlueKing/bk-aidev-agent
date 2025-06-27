# -*- coding: utf-8 -*-
import enum
import os
from typing import Optional

import environs


class SettingEnvVariables(enum.Enum):
    APP_CODE = "BKPAAS_APP_ID"
    SECRET_KEY = "BKPAAS_APP_SECRET"

    # apigateway
    BK_API_URL_TMPL = "BK_API_URL_TMPL"
    BK_APIGW_STAGE = "BK_APIGW_STAGE"
    BK_AIDEV_GATEWAY_NAME = "AIDEV_GATEWAY_NAME"
    BK_AIDEV_APIGW_ENDPOINT = "BK_AIDEV_APIGW_ENDPOINT"


class Settings(object):
    _instance: Optional["Settings"] = None

    def __init__(
        self,
        settings=None,  # type: Any
    ):
        self._settings = settings
        self._defaults = {}  # type: Dict[str, Any]
        self._resolved = {}  # type: Dict[str, Any]

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = Settings()
        return cls._instance

    def __getattr__(self, key: str) -> any:
        """
        get settings from self
        """
        return self.get(key)

    def get(
        self,
        key,  # type: str
        default=None,  # type: Any
    ):
        # type: (...) -> Any
        """
        Returns the specified value, if not found, return to the default value
        """

        # If the key has been hold in the cache, return it directly
        if key in self._resolved:
            return self._resolved[key]

        if self._settings and hasattr(self._settings, key):
            value = self._resolved[key] = getattr(self._settings, key)
            return value

        if key in self._defaults:
            value = self._resolved[key] = self._defaults[key]
            return value

        if getattr(SettingEnvVariables, key, None):
            value = os.environ.get(key)
            return value if value else default

        return default

    def set(self, key, value):
        """
        Set the value of the key
        """

        self._resolved[key] = value

    def set_settings(self, settings_):
        self._settings = settings_

    def set_defaults(self, defaults_):
        """
        Set the default value of the key
        """
        if defaults_:
            self._defaults.update(defaults_)

    def reset(self):
        """
        Reset the resolved cache
        """

        self._resolved.clear()


settings = Settings.get_instance()


def update_django_settings(django_settings=None):
    """
    将当前的 settings 配置 更新到 Django 的 settings
    """
    if django_settings is None:
        from django.conf import settings as django_settings  # noqa
    for attr, value in settings._resolved.items():
        setattr(django_settings, attr, value)


env = environs.Env()
env.read_env()
existed_keys = list(locals().keys())
existed_keys.append("existed_keys")


# begin: 配置
ENABLE_SIMILARITY_MODEL = env.bool("ENABLE_SIMILARITY_MODEL", False)
BKAIDEV_FINE_GRAINED_SCORE_TYPE = (
    env.str("BKAIDEV_FINE_GRAINED_SCORE_TYPE", "LLM") if not ENABLE_SIMILARITY_MODEL else "EXCLUSIVE_SIMILARITY_MODEL"
)
BKAIDEV_TOP_K = env.int("BKAIDEV_TOP_K", 10)
BKAIDEV_KNOWLEDGE_RESOURCE_REJECT_THRESHOLD = env.str("BKAIDEV_KNOWLEDGE_RESOURCE_REJECT_THRESHOLD", "0.0001,0.1")
LLM_GW_ENDPOINT = env.str("LLM_GW_ENDPOINT", "") or env.str("LLM_GATEWAY_URL", "")
APP_CODE = env.str("BK_AIDEV_AGENT_APP_CODE", "") or env.str("BKPAAS_APP_ID", "") or env.str("APP_ID", "")
SECRET_KEY = env.str("BK_AIDEV_AGENT_APP_SECRET", "") or env.str("BKPAAS_APP_SECRET", "") or env.str("APP_TOKEN", "")
BK_AIDEV_GATEWAY_NAME = env.str("AIDEV_GATEWAY_NAME", "bkaidev")
BK_AIDEV_APIGW_ENDPOINT = env.str("BK_AIDEV_APIGW_ENDPOINT", "")
BK_APIGW_STAGE = env.str("BK_APIGW_STAGE", "") or env.str("BKAIDEV_RESOURCE_STAGE", "prod")
INTENT_RECOGNITION_GLOBAL_LLM_MODEL_NAME = env.str("INTENT_RECOGNITION_GLOBAL_LLM_MODEL_NAME", "hunyuan")

# end: 配置


settings.set_defaults({k: v for k, v in locals().items() if k not in existed_keys})
