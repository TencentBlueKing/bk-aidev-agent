# -*- coding: utf-8 -*-
# DO NOT MODIFY THIS FILE UNLESS YOU KNOW WHAT YOU ARE DOING !!!

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bk_plugin.patch.plugin")
    os.environ.setdefault("BK_APP_CONFIG_PATH", "bk_plugin_runtime.config")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
