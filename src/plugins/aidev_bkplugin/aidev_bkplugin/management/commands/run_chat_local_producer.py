import json
import sys
from logging import getLogger

from django.core.management.base import BaseCommand

from aidev_bkplugin.services.chat_tasks import run_chat

try:
    from opentelemetry import trace
except ImportError:
    trace = None


logger = getLogger(__name__)


class Command(BaseCommand):
    help = "Execute one local chat producer from the inherited input stream."
    requires_system_checks = []

    def handle(self, *args, **options):
        try:
            run_chat(**json.load(sys.stdin), backend="local")
        finally:
            provider = trace.get_tracer_provider() if trace else None
            flush = getattr(provider, "force_flush", None)
            if flush:
                try:
                    if not flush(timeout_millis=2000):
                        logger.warning("Timed out flushing local producer spans")
                except Exception:
                    logger.exception("Failed to flush local producer spans")
