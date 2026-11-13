"""任务级执行策略包装器，复用原资源管理器且不修改全局实例。"""

from typing import Any

from aidev_agent.packages.resource_manager.registry import ResourceManagerProtocol
from aidev_agent.services.messages_handler.producer import ProducerRunner, run_producer_inline


class WorkerResourceManager:
    """只覆盖 producer 策略，认证、client 缓存和资源方法仍由原实现提供。"""

    def __init__(self, resources: ResourceManagerProtocol):
        self._resources = resources

    def get_producer_runner(self) -> ProducerRunner:
        return run_producer_inline

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resources, name)
