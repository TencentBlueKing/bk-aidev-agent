"""可选 producer 策略：本地执行，或在 Chat 副作用发生前委托远端执行。"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from threading import Thread
from typing import Any

from typing_extensions import Protocol, runtime_checkable


class RemoteProducerRunner(ABC):
    """Delegate before Chat execution mutates session history or checkpoint state."""

    @abstractmethod
    def execute_chat(self, agent: Any, execute_kwargs: Any) -> Any:
        raise NotImplementedError


@dataclass
class ProducerOnlyRunner:
    """Run production in a worker without registering a competing consumer."""

    on_started: Callable[[str, str], None]

    def __call__(self, produce: Callable[[], None]) -> None:
        produce()


ProducerRunner = Callable[[Callable[[], None]], Thread | None] | RemoteProducerRunner


def run_producer_inline(produce: Callable[[], None]) -> None:
    """在当前 worker 执行，直到 producer 完成；不将 live generator 发送到任务队列。"""
    produce()


@runtime_checkable
class ProducerExecutionResources(Protocol):
    """Resource Manager 的可选能力；不扩展原资源协议的必需方法集合。"""

    def get_producer_runner(self) -> ProducerRunner | None:
        """返回执行策略；None 保留默认线程行为，RemoteProducerRunner 仅用于 Chat。"""
        ...


def resolve_producer_runner(resource_manager: object | None) -> ProducerRunner | None:
    """兼容没有新能力的旧实现，包括不继承 SDK 基类的鸭子类型实现。"""
    if isinstance(resource_manager, ProducerExecutionResources):
        return resource_manager.get_producer_runner()
    return None
