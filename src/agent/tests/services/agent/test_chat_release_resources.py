# -*- coding: utf-8 -*-
"""ChatCompletionAgent.release_resources 回归测试。

统一走 ``resolver.close()``，销毁语义由 resolver 按延迟销毁策略分流：
- 延迟销毁启用：close 移交所有权给 LifecycleManager（defer），不立即销毁（D-16）；
- 未启用：立即销毁（D-02）；
- release 幂等：多次调用 resolver.close 多次（close 自身幂等），resolver 置 None。
"""

from __future__ import annotations

import unittest
from unittest import mock

from aidev_agent.core.tools.runtime_tools.provider import RuntimeBackendResolver
from aidev_agent.core.tools.runtime_tools.types import RuntimeBackend
from aidev_agent.services.agent.chat import ChatCompletionAgent


class TestReleaseResources(unittest.TestCase):
    """release_resources 统一走 resolver.close()（销毁语义由 resolver 分流）。"""

    def test_release_resources_calls_close_and_clears_resolver(self):
        """release_resources 调 resolver.close() 一次，并将 resolver 置 None。"""
        agent = ChatCompletionAgent()
        resolver = mock.Mock(spec=RuntimeBackendResolver)
        agent.runtime_backend_resolver = resolver

        agent.release_resources()

        resolver.close.assert_called_once_with()
        self.assertIsNone(agent.runtime_backend_resolver)

    def test_release_resources_idempotent(self):
        """resolver 为 None 时（已释放）重复调用无副作用。"""
        agent = ChatCompletionAgent()
        resolver = mock.Mock(spec=RuntimeBackendResolver)
        agent.runtime_backend_resolver = resolver

        agent.release_resources()
        agent.release_resources()

        resolver.close.assert_called_once_with()  # 第二次直接跳过


class _CloseTrackingBackend(RuntimeBackend):
    """用于 close 幂等测试的真实 RuntimeBackend 子类。

    ExitStack 通过 __exit__ 触发 close()，记录调用次数验证幂等。
    """

    def __init__(self) -> None:
        self.close_count = 0

    def close(self) -> None:  # type: ignore[override]
        self.close_count += 1


class TestCloseIdempotent(unittest.TestCase):
    """RuntimeBackendResolver.close() 幂等性回归（D-27）。"""

    def test_close_idempotent_preserved(self):
        """close() 调两次：第二次无异常，backend.close 被调一次（幂等）。"""
        resolver = RuntimeBackendResolver(default_runtime="local")
        backend = _CloseTrackingBackend()
        resolver.register_runtime("paas_sandbox_skill", backend)
        resolver.resolve_backend("paas_sandbox_skill")  # 触发 enter_context

        # 第一次 close：触发 ExitStack 关闭（调用 backend.close）
        resolver.close()
        self.assertEqual(backend.close_count, 1)
        # 第二次 close：幂等，无异常，不重复 close
        resolver.close()  # 不应抛异常
        self.assertEqual(backend.close_count, 1)  # 仍为 1（ExitStack 已重建）


if __name__ == "__main__":
    unittest.main()
