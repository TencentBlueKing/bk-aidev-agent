"""可选 producer 策略：默认线程或当前 worker 内执行。"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Thread

from typing_extensions import Protocol, runtime_checkable

from .base import BaseMessageQueueHandler


@dataclass
class ProducerOnlyRunner:
    """Run production in a worker without registering a competing consumer."""

    on_started: Callable[[str, str], None]

    locked_session: str | None = field(default=None, init=False)

    @contextmanager
    def claim(self, handler: BaseMessageQueueHandler, session_code: str) -> Iterator[None]:
        """Hold ownership across worker preparation and inline production."""
        if not handler.acquire_producer(session_code):
            raise RuntimeError("Worker could not acquire the producer lock")
        self.locked_session = session_code
        try:
            yield
        finally:
            self.locked_session = None
            handler.release_producer(session_code)

    def __call__(self, produce: Callable[[], None]) -> None:
        produce()


ProducerRunner = Callable[[Callable[[], None]], Thread | None]


def run_producer_inline(produce: Callable[[], None]) -> None:
    """在当前 worker 执行，直到 producer 完成；不将 live generator 发送到任务队列。"""
    produce()


@runtime_checkable
class ProducerExecutionResources(Protocol):
    """Resource Manager 的可选能力；不扩展原资源协议的必需方法集合。"""

    def get_producer_runner(self) -> ProducerRunner | None:
        """返回执行策略；None 保留默认线程行为。"""
        ...


def resolve_producer_runner(resource_manager: object | None) -> ProducerRunner | None:
    """兼容没有新能力的旧实现，包括不继承 SDK 基类的鸭子类型实现。"""
    if isinstance(resource_manager, ProducerExecutionResources):
        return resource_manager.get_producer_runner()
    return None
