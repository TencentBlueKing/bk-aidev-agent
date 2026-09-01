"""Side-effect-free Django app configs for the wxbot test suite."""

from django.apps import AppConfig


class AidevBkpluginTestConfig(AppConfig):
    """Register bkplugin models without running its production startup hooks."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "aidev_bkplugin"
    label = "aidev_bkplugin"


class AidevWxbotTestConfig(AppConfig):
    """Register wxbot models without starting transport services."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "aidev_wxbot"
    label = "aidev_wxbot"
