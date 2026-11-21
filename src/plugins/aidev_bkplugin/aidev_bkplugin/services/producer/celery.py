from aidev_agent.config import settings as agent_settings
from celery import current_app

CHAT_TASK_NAME = "aidev_bkplugin.run_chat_producer"


def enqueue(payload: dict, queue_timeout: int) -> None:
    current_app.send_task(
        CHAT_TASK_NAME,
        kwargs=payload,
        task_id=payload["task_id"],
        queue=agent_settings.BKAI_AGENT_TASK,
        expires=queue_timeout,
    )
