from aidev_agent.utils.tracing import recording_span

from . import celery, local

try:
    from opentelemetry.trace import StatusCode
except ImportError:
    StatusCode = None


def submit(payload: dict, queue_timeout: int) -> str:
    with recording_span("bkplugin_chat_producer_route", record_exception=False, use_global_tracer=True) as span:
        try:
            if local.try_start_local_producer(payload):
                span.set_attribute("bkplugin.chat.producer.backend", "local")
                return "local"
            span.set_attribute("bkplugin.chat.producer.backend", "celery")
            celery.enqueue(payload, queue_timeout)
            return "celery"
        except Exception as exc:
            span.set_attribute("error.type", type(exc).__name__)
            if StatusCode is not None and span.is_recording():
                span.set_status(StatusCode.ERROR)
            raise
