import json
import os
import sys
import time
from logging import getLogger

from aidev_agent.utils.tracing import propagated_trace_context
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

    def add_arguments(self, parser):
        parser.add_argument("--launch-time-ns", type=int)

    def handle(self, *args, **options):
        entered_at = time.time_ns()
        try:
            payload = json.load(sys.stdin)
            launch_context = payload.pop("launch_context", None)
            if trace is not None and launch_context and options.get("launch_time_ns") is not None:
                with propagated_trace_context(launch_context):
                    startup = trace.get_tracer(__name__).start_span(
                        "bkplugin.chat.local.startup",
                        start_time=options["launch_time_ns"],
                        attributes={
                            "task_id": payload["task_id"],
                            "producer_backend": "local",
                            "process_pid": os.getpid(),
                        },
                    )
                    startup.end(end_time=entered_at)
            run_chat(**payload, backend="local")
        finally:
            provider = trace.get_tracer_provider() if trace else None
            flush = getattr(provider, "force_flush", None)
            if flush:
                try:
                    if not flush(timeout_millis=2000):
                        logger.warning("Timed out flushing local producer spans")
                except Exception:
                    logger.exception("Failed to flush local producer spans")
