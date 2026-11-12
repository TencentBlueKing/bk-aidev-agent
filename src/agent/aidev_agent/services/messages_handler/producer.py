"""进程内 producer 执行策略；跨进程调度应先重建 Agent 再注入策略。"""

from collections.abc import Callable
from threading import Thread

ProducerRunner = Callable[[Callable[[], None]], Thread | None]


def run_producer_inline(produce: Callable[[], None]) -> None:
    """在当前 worker 执行，直到 producer 完成；不将 live generator 发送到任务队列。"""
    produce()
