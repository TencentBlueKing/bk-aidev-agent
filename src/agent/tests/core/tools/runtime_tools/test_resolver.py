# -*- coding: utf-8 -*-
"""RuntimeBackendResolver 和 RuntimeBackend 基类生命周期测试。

测试范围：
1. RuntimeBackend 基类提供 close()/aclose()/__enter__/__exit__/__aenter__/__aexit__
2. PaasSandboxBackend.close() 委托给 kill()
3. E2BSandboxBackend.close() 委托给 kill()
4. FilesystemBackend.close() 为空操作
5. RuntimeBackendResolver.close() 通过 ExitStack 关闭所有已解析后端
6. RuntimeBackendResolver.close() 是幂等的
7. RuntimeBackendResolver.close() 即使某个后端关闭失败也继续执行
8. register_runtime 使重新注册的运行时生效
9. _resolve_backend 对未知 runtime 抛出 ValueError
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.tools.runtime_tools.provider import RuntimeBackendResolver
from aidev_agent.core.tools.runtime_tools.types import RuntimeBackend


class TestRuntimeBackendBaseClass(unittest.TestCase):
    """测试 1：RuntimeBackend 基类提供所有必需方法。"""

    def test_has_close(self):
        assert hasattr(RuntimeBackend, "close")

    def test_has_aclose(self):
        assert hasattr(RuntimeBackend, "aclose")

    def test_has_enter(self):
        assert hasattr(RuntimeBackend, "__enter__")

    def test_has_exit(self):
        assert hasattr(RuntimeBackend, "__exit__")

    def test_has_aenter(self):
        assert hasattr(RuntimeBackend, "__aenter__")

    def test_has_aexit(self):
        assert hasattr(RuntimeBackend, "__aexit__")

    def test_close_is_noop(self):
        backend = RuntimeBackend()
        # close() 应不抛出异常
        backend.close()

    def test_context_manager(self):
        backend = RuntimeBackend()
        with backend as ctx:
            assert ctx is backend

    def test_file_methods_raise_not_implemented(self):
        backend = RuntimeBackend()
        with self.assertRaises(NotImplementedError):
            backend.ls_info("/tmp")
        with self.assertRaises(NotImplementedError):
            backend.read("/tmp/file.txt")
        with self.assertRaises(NotImplementedError):
            backend.write("/tmp/file.txt", "content")
        with self.assertRaises(NotImplementedError):
            backend.edit("/tmp/file.txt", "old", "new")
        with self.assertRaises(NotImplementedError):
            backend.glob_info("*.py")
        with self.assertRaises(NotImplementedError):
            backend.grep_raw("pattern")
        with self.assertRaises(NotImplementedError):
            backend.execute("ls")


class TestPaasBackendCloseCallsKill(unittest.TestCase):
    """测试 2：PaasSandboxBackend.close() 委托给 kill()。"""

    def test_close_calls_kill(self):
        from unittest.mock import MagicMock

        from aidev_agent.core.tools.runtime_tools.paas_backend import PaasSandboxBackend

        backend = PaasSandboxBackend(
            client=MagicMock(),
            snapshot="test-snapshot",
            snapshot_entrypoint=["python", "-m", "server"],
            env_vars={},
        )
        backend.kill = MagicMock()
        backend.close()
        backend.kill.assert_called_once()


class TestE2BBackendCloseCallsKill(unittest.TestCase):
    """测试 3：E2BSandboxBackend.close() 委托给 kill()。"""

    def test_close_calls_kill(self):
        from aidev_agent.core.tools.runtime_tools.e2b_backend import E2BSandboxBackend

        backend = E2BSandboxBackend()
        backend.kill = MagicMock()
        backend.close()
        backend.kill.assert_called_once()


class TestLocalBackendCloseIsNoop(unittest.TestCase):
    """测试 4：FilesystemBackend.close() 为空操作。"""

    def test_close_is_noop(self):
        from aidev_agent.core.tools.runtime_tools.local_backend import FilesystemBackend

        backend = FilesystemBackend()
        # close() 应不抛出异常
        backend.close()


class TestResolverCloseViaExitStack(unittest.TestCase):
    """测试 5：RuntimeBackendResolver.close() 通过 ExitStack 关闭所有已解析后端。"""

    def test_close_calls_backend_close(self):
        resolver = RuntimeBackendResolver()
        # 创建真实 RuntimeBackend 子类实例并 mock close()
        backend = RuntimeBackend()
        backend.close = MagicMock()
        resolver.register_runtime("test", backend)
        # 解析后端以注册到 ExitStack
        resolver._resolve_backend("test")
        # 调用 close
        resolver.close()
        # ExitStack 的 close 会调用 __exit__，进而调用 close()
        backend.close.assert_called()


class TestResolverCloseIdempotent(unittest.TestCase):
    """测试 6：RuntimeBackendResolver.close() 是幂等的。"""

    def test_close_twice_no_error(self):
        resolver = RuntimeBackendResolver()
        backend = RuntimeBackend()
        backend.close = MagicMock()
        resolver.register_runtime("test", backend)
        resolver._resolve_backend("test")
        # 调用两次
        resolver.close()
        resolver.close()  # 第二次不应抛出异常


class TestResolverCloseContinuesOnError(unittest.TestCase):
    """测试 7：RuntimeBackendResolver.close() 即使某个后端关闭失败也继续执行。"""

    def test_close_continues_on_error(self):
        resolver = RuntimeBackendResolver()
        # 第一个后端 close 抛出异常
        backend1 = RuntimeBackend()
        backend1.close = MagicMock(side_effect=RuntimeError("close failed"))
        # 第二个后端 close 正常
        backend2 = RuntimeBackend()
        backend2.close = MagicMock()
        resolver.register_runtime("backend1", backend1)
        resolver.register_runtime("backend2", backend2)
        resolver._resolve_backend("backend1")
        resolver._resolve_backend("backend2")
        # close 不应抛出异常
        resolver.close()
        # 至少有一个后端的 close 被调用了
        # ExitStack 按注册逆序关闭，backend2 先关闭
        assert backend2.close.called or backend1.close.called


class TestRegisterRuntime(unittest.TestCase):
    """测试 8：register_runtime 同名同实例幂等，同名异实例抛错（CR）。"""

    def test_register_same_instance_idempotent(self):
        resolver = RuntimeBackendResolver()
        backend_a = RuntimeBackend()
        resolver.register_runtime("test", backend_a)
        resolver.register_runtime("test", backend_a)  # 幂等返回
        assert resolver._resolve_backend("test") is backend_a

    def test_register_different_instance_raises(self):
        resolver = RuntimeBackendResolver()
        backend_a = RuntimeBackend()
        backend_b = RuntimeBackend()
        resolver.register_runtime("test", backend_a)
        # 同名异实例：抛 ValueError，原注册不被覆盖
        with pytest.raises(ValueError) as ctx:
            resolver.register_runtime("test", backend_b)
        assert "test" in str(ctx.value)
        assert resolver._resolve_backend("test") is backend_a


class TestResolveBackendUnknownRuntime(unittest.TestCase):
    """测试 9：_resolve_backend 对未知 runtime 抛出 ValueError。"""

    def test_unknown_runtime_raises_value_error(self):
        resolver = RuntimeBackendResolver()
        with self.assertRaises(ValueError) as ctx:
            resolver._resolve_backend("nonexistent")
        assert "nonexistent" in str(ctx.exception)


if __name__ == "__main__":
    unittest.main()
