# -*- coding: utf-8 -*-
"""RuntimeBackend save / load 单元测试（load 为实例方法，挂载式复用）。

测试范围：
1. PaasSandboxBackend.save 只返回 sandbox_id（CR：executor_info/construct_params 不允许保存）
2. PaasSandboxBackend.load 实例方法：就地覆盖 _sandbox_id；payload 为 {} 时 no-op（原沙箱未拉起过）
3. PaasSandboxBackend.save 在 sandbox_id 为 None 时导出 {}（不抛异常）
4. E2BSandboxBackend.save 返回 sandbox_info 内容；未创建时导出 {}（不抛异常）
5. E2BSandboxBackend.load 实例方法：就地重建 self._sandbox（跳过 Sandbox.create）；payload {} 时 no-op
6. FilesystemBackend.save/load 往返（root_dir/virtual_mode/max_file_size_mb）

注意：PaaS 测试用 MagicMock 作为 client；E2B 测试 mock e2b_code_interpreter.Sandbox
避免真实创建沙箱。
"""

from __future__ import annotations

import unittest
from unittest import mock

from aidev_agent.core.tools.runtime_tools.e2b_backend import E2BSandboxBackend
from aidev_agent.core.tools.runtime_tools.local_backend import FilesystemBackend
from aidev_agent.core.tools.runtime_tools.paas_backend import PaasSandboxBackend


def _make_paas_backend(sandbox_id="sbx-1"):
    """构造一个 PaasSandboxBackend（用 MagicMock 作为 client）。"""
    return PaasSandboxBackend(
        app_code="app1",
        bk_username="user1",
        client=mock.MagicMock(),
        snapshot="snap",
        snapshot_entrypoint=["python"],
        env_vars={"A": "1"},
        sandbox_id=sandbox_id,
        workspace="/ws",
        ttl_seconds=3600,
        extra_sensitive_values=["sec"],
    )


def _make_e2b_sandbox_info():
    """构造一个 E2B sandbox_info 字典。"""
    return {
        "sandbox_id": "e2b-1",
        "sandbox_domain": "dom",
        "envd_access_token": "tok",
        "envd_version": "0.1.0",
        "traffic_access_token": None,
    }


class TestPaasSaveShape(unittest.TestCase):
    """测试 1：PaasSandboxBackend.save 只返回 sandbox_id。"""

    def test_paas_save_shape(self):
        """save 只含 sandbox_id；executor_info/construct_params 不允许出现（CR）。"""
        backend = _make_paas_backend()
        payload = backend.save()

        self.assertEqual(payload, {"sandbox_id": "sbx-1"})


class TestPaasLoadInstanceAttach(unittest.TestCase):
    """测试 2：load 为实例方法，就地挂载。"""

    def test_paas_load_overrides_sandbox_id(self):
        """load 覆盖 self._sandbox_id；client 保持本实例构造时来源（不来自 payload）。"""
        backend = _make_paas_backend(sandbox_id="sbx-old")
        client = backend.client

        backend.load({"sandbox_id": "sbx-new"})

        self.assertEqual(backend._sandbox_id, "sbx-new")
        self.assertIs(backend.client, client)

    def test_paas_load_missing_sandbox_id_noop(self):
        """payload 为 {}（原沙箱未真正拉起过）时 no-op，保持 lazy。"""
        backend = _make_paas_backend(sandbox_id=None)
        backend.load({})
        self.assertIsNone(backend._sandbox_id)  # 未创建，保持 lazy

    def test_paas_load_noop_keeps_existing(self):
        """payload 缺 sandbox_id 时 no-op，不覆盖已有挂载。"""
        backend = _make_paas_backend(sandbox_id="sbx-keep")
        backend.load({})
        self.assertEqual(backend._sandbox_id, "sbx-keep")


class TestPaasSaveWithoutSandbox(unittest.TestCase):
    """测试 3：save 在 sandbox_id 为 None 时导出 {}（不抛异常）。"""

    def test_paas_save_without_sandbox_returns_empty(self):
        """sandbox_id 为 None（沙箱未真正拉起过）时 save 返回 {}。"""
        backend = _make_paas_backend(sandbox_id=None)
        self.assertEqual(backend.save(), {})


class TestE2bSaveShape(unittest.TestCase):
    """测试 4：E2BSandboxBackend.save 返回结构。"""

    def test_e2b_save_shape(self):
        """save 返回 sandbox_info 内容。"""
        info = _make_e2b_sandbox_info()
        sandbox = mock.MagicMock()
        sandbox.sandbox_id = info["sandbox_id"]
        sandbox.sandbox_domain = info["sandbox_domain"]
        sandbox._envd_access_token = info["envd_access_token"]
        sandbox._envd_version = info["envd_version"]
        sandbox.traffic_access_token = info["traffic_access_token"]

        backend = E2BSandboxBackend.__new__(E2BSandboxBackend)
        backend._sandbox = sandbox

        payload = backend.save()

        self.assertEqual(payload, info)

    def test_e2b_save_uncreated_returns_empty(self):
        """沙箱未创建（sandbox_info 为 None）时 save 返回 {}，不抛异常。"""
        backend = E2BSandboxBackend(template="t", timeout=1)
        self.assertIsNone(backend.sandbox_info)
        self.assertEqual(backend.save(), {})


class TestE2bLoadInstanceAttach(unittest.TestCase):
    """测试 5：load 为实例方法，就地重建 self._sandbox（跳过 Sandbox.create）。"""

    def test_e2b_load_rebuilds_sandbox_inplace(self):
        """load 用 sandbox_info 构造 Sandbox 并覆盖 self._sandbox；挂载后续期远端 TTL。"""
        info = _make_e2b_sandbox_info()
        backend = E2BSandboxBackend(template="t", timeout=1)
        self.assertIsNone(backend._sandbox)  # lazy：构造时不创建

        with mock.patch("aidev_agent.core.tools.runtime_tools.e2b_backend.Sandbox") as mock_sandbox_cls:
            backend.load(info)

        self.assertIs(backend._sandbox, mock_sandbox_cls.return_value)
        kwargs = mock_sandbox_cls.call_args.kwargs
        self.assertEqual(kwargs["sandbox_id"], "e2b-1")
        self.assertEqual(kwargs["sandbox_domain"], "dom")
        self.assertIsNone(backend._pending_sandbox_env)  # 挂载后创建参数失效
        # 挂载即续期：远端 TTL 续到本 backend 配置的 timeout
        backend._sandbox.set_timeout.assert_called_once_with(1)

    def test_e2b_load_empty_payload_noop(self):
        """payload 为 {}（原沙箱未真正拉起过）时 no-op，不创建沙箱。"""
        backend = E2BSandboxBackend(template="t", timeout=1)
        with mock.patch("aidev_agent.core.tools.runtime_tools.e2b_backend.Sandbox") as mock_sandbox_cls:
            backend.load({})
        mock_sandbox_cls.assert_not_called()  # 不创建沙箱
        self.assertIsNone(backend._sandbox)  # 保持 lazy

    def test_e2b_run_self_heals_on_sandbox_not_found(self):
        """CR-A：挂载沙箱失效（NotFound）时丢弃引用重建并重试一次。"""
        from e2b.exceptions import SandboxNotFoundException

        backend = E2BSandboxBackend(template="t", timeout=1)
        dead = mock.MagicMock()
        dead.commands.run.side_effect = SandboxNotFoundException("gone")
        backend._sandbox = dead  # 模拟已挂载的失效沙箱

        alive = mock.MagicMock()
        alive.commands.run.return_value = {"stdout": "ok", "exit_code": 0}

        with mock.patch("aidev_agent.core.tools.runtime_tools.e2b_backend.Sandbox") as mock_sandbox_cls:
            mock_sandbox_cls.create.return_value = alive
            result = backend._run("echo hi")

        self.assertEqual(result.stdout, "ok")
        self.assertIs(backend._sandbox, alive)  # 已重建
        mock_sandbox_cls.create.assert_called_once()  # 重建发生
        create_kwargs = mock_sandbox_cls.create.call_args.kwargs
        self.assertEqual(create_kwargs["timeout"], 1)  # 重建沿用 backend 配置的 timeout


class TestFilesystemSaveLoad(unittest.TestCase):
    """测试 6：FilesystemBackend.save/load 往返（实例方法，就地挂载）。"""

    def test_filesystem_save_load_roundtrip(self):
        """save 保存 cwd/virtual_mode/max_file_size_mb，load 就地覆盖。"""
        backend = FilesystemBackend(root_dir="/tmp/ws", virtual_mode=True, max_file_size_mb=5)
        payload = backend.save()

        self.assertEqual(payload["root_dir"], str(backend.cwd))
        self.assertTrue(payload["virtual_mode"])
        self.assertEqual(payload["max_file_size_mb"], 5)

        other = FilesystemBackend()
        other.load(payload)
        self.assertEqual(str(other.cwd), str(backend.cwd))
        self.assertTrue(other.virtual_mode)
        self.assertEqual(other.max_file_size_bytes, 5 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
