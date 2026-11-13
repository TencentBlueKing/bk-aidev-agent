"""进程内 producer 执行策略；跨进程调度应先重建 Agent 再注入策略。"""

from collections.abc import Callable
from threading import Thread

from typing_extensions import Protocol, runtime_checkable

ProducerRunner = Callable[[Callable[[], None]], Thread | None]


def run_producer_inline(produce: Callable[[], None]) -> None:
    """在当前 worker 执行，直到 producer 完成；不将 live generator 发送到任务队列。"""
    produce()


@runtime_checkable
class ProducerExecutionResources(Protocol):
    """Resource Manager 的可选能力；不扩展原资源协议的必需方法集合。"""

    def get_producer_runner(self) -> ProducerRunner | None:
        """返回进程内执行策略；None 保留默认线程行为。"""
        ...


def resolve_producer_runner(resource_manager: object | None) -> ProducerRunner | None:
    """兼容没有新能力的旧实现，包括不继承 SDK 基类的鸭子类型实现。"""
    if isinstance(resource_manager, ProducerExecutionResources):
        return resource_manager.get_producer_runner()
    return None
