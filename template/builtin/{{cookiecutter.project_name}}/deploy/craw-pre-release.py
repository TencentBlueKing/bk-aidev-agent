#!/usr/bin/env python3
"""Run the builtin plugin pre-release commands after a single Django setup."""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bk_plugin.patch.plugin")

import django
from django.core.management import call_command


def main() -> None:
    django.setup()
    call_command("migrate", interactive=False)
    call_command("createcachetable")
    call_command("sync_apigateway_if_changed")


if __name__ == "__main__":
    main()
