import json
import sys

from django.core.management.base import BaseCommand

from aidev_bkplugin.services.chat_tasks import run_chat


class Command(BaseCommand):
    help = "Execute one local chat producer from the inherited input stream."
    requires_system_checks = []

    def handle(self, *args, **options):
        run_chat(**json.load(sys.stdin))
