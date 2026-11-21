from aidev_agent.utils.tracing import recording_span

from . import celery, local


def submit(payload: dict, queue_timeout: int) -> None:
    with recording_span("bkplugin.chat.producer.dispatch", record_exception=False, use_global_tracer=True) as span:
        if local.try_start_local_producer(payload):
            span.set_attribute("bkplugin.chat.producer.backend", "local")
            return
        span.set_attribute("bkplugin.chat.producer.backend", "celery")
        celery.enqueue(payload, queue_timeout)
