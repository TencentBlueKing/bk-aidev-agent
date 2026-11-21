from . import celery, local


def submit(payload: dict, queue_timeout: int) -> None:
    if not local.try_start_local_producer(payload):
        celery.enqueue(payload, queue_timeout)
