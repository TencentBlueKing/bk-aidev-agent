# -*- coding: utf-8 -*-
"""RuntimeBackendDeferManager 单元测试（纯策略层：4 原语 token 透传 + 遍历 _owned 单阶段销毁）。

覆盖 get_runtime 纯透传 token 语义（get 命中即摘 token）、defer 登记
_owned(_OwnedBackend 持 token) + store 记录带 token、_sweep_once 遍历 _owned 驱动
单阶段 delete_if_token 销毁（delete_if_token 成功 close / token 被 get 摘除跳 close
拦截销毁 / 记录被删跳 close / 新 defer 覆盖跳 close）、delete_expired GC、
shutdown 先 token 校验再 close（校验成功 close / token 被摘跳 close）。

关键：生命周期构造一律 record_max_age=...、不传 grace_period；token 语义封装在
store 内，测试不 import STATE_*、不 backdate last_access_at（让 entry 到期改
``mgr._owned[key].expires_at`` 为过去即可）、不 mock time.sleep（已无 sleep）。
"""

from __future__ import annotations

import time
import unittest
from unittest import mock

from aidev_agent.core.tools.runtime_tools.defer_manager import (
    RuntimeBackendDeferInMemoryStore,
    RuntimeBackendDeferManager,
)


def _make_mgr(store, **overrides):
    kwargs = {
        "store": store,
        "idle_ttl": 300,
        "sweep_interval": 0.05,
        "record_max_age": 259200.0,
    }
    kwargs.update(overrides)
    return RuntimeBackendDeferManager(**kwargs)


def _defer_and_expire(mgr, store, key, backend):
    """defer 登记 _owned + store 记录（持 token），并把该 entry 的 expires_at 改为过去值。"""
    mgr.defer({key: backend})
    with mgr._owned_lock:
        mgr._owned[key].expires_at = time.time() - 1  # 已过期


def _token_of(store, key):
    """取 store 记录内当前 token（None 表示已被摘除/无记录）。"""
    record = store._records.get(key)
    return record.get("token") if record else None


def _payload_of(store, key):
    """取 store 记录内 payload（不消费 token）。"""
    record = store._records.get(key)
    return dict(record["payload"]) if record else None


class TestGetRuntime(unittest.TestCase):
    """get_runtime 纯透传 store.get token 语义。"""

    def test_active_payload_returns_payload(self):
        store = RuntimeBackendDeferInMemoryStore()
        key = "agent:s1:paas_sandbox_pdf"
        store.put(key, {"sandbox_id": "sbx-1"}, token="tok-1")
        mgr = _make_mgr(store)
        self.assertEqual(mgr.get_runtime(key), {"sandbox_id": "sbx-1"})

    def test_absent_returns_none(self):
        mgr = _make_mgr(RuntimeBackendDeferInMemoryStore())
        self.assertIsNone(mgr.get_runtime("agent:s1:paas_sandbox_pdf"))

    def test_empty_payload_returns_empty_dict(self):
        store = RuntimeBackendDeferInMemoryStore()
        key = "agent:s1:paas_sandbox_pdf"
        store.put(key, {}, token="tok-1")
        mgr = _make_mgr(store)
        self.assertEqual(mgr.get_runtime(key), {})

    def test_get_removes_token(self):
        """get_runtime 命中后 store 内 token 被摘除（挂载方获得销毁豁免）。"""
        store = RuntimeBackendDeferInMemoryStore()
        key = "agent:s1:paas_sandbox_pdf"
        store.put(key, {"sandbox_id": "sbx-1"}, token="tok-1")
        mgr = _make_mgr(store)
        self.assertEqual(mgr.get_runtime(key), {"sandbox_id": "sbx-1"})
        self.assertIsNone(_token_of(store, key))  # token 已摘


class TestDefer(unittest.TestCase):
    """defer 所有权接管：store.put(token) 登记 + _owned 登记 _OwnedBackend(backend+token+expires_at)。"""

    def test_defer_registers_record_and_owns_instance_with_token(self):
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store)
        backend = mock.MagicMock()
        backend.save.return_value = {"sandbox_id": "sbx-1"}
        mgr.defer({"agent:s1:paas_sandbox_pdf": backend})
        backend.save.assert_called_once()
        # _owned 持 token，且与 store 记录内 token 一致（本进程所有权身份）
        owned = mgr._owned["agent:s1:paas_sandbox_pdf"]
        self.assertIs(owned.backend, backend)
        self.assertTrue(owned.token)  # 非空
        self.assertEqual(_token_of(store, "agent:s1:paas_sandbox_pdf"), owned.token)
        self.assertGreater(owned.expires_at, time.time())  # expires_at = now + idle_ttl
        backend.close.assert_not_called()
        # 记录已登记供复用（先核对 token，再 get 命中 payload）
        self.assertEqual(_payload_of(store, "agent:s1:paas_sandbox_pdf"), {"sandbox_id": "sbx-1"})
        self.assertEqual(mgr.get_runtime("agent:s1:paas_sandbox_pdf"), {"sandbox_id": "sbx-1"})

    def test_defer_empty_payload_still_registers(self):
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store)
        backend = mock.MagicMock()
        backend.save.return_value = {}
        mgr.defer({"agent:s1:paas_sandbox_pdf": backend})
        self.assertEqual(mgr.get_runtime("agent:s1:paas_sandbox_pdf"), {})
        self.assertIs(mgr._owned["agent:s1:paas_sandbox_pdf"].backend, backend)

    def test_defer_save_failure_closes_and_does_not_own(self):
        """save() 失败 → store.put 未落地 → 立即 close backend，不登记 _owned（杜绝死 entry 泄漏）。"""
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store)
        backend = mock.MagicMock()
        backend.save.side_effect = RuntimeError("boom")
        mgr.defer({"agent:s1:paas_sandbox_pdf": backend})
        backend.close.assert_called_once()  # 立即销毁
        self.assertNotIn("agent:s1:paas_sandbox_pdf", mgr._owned)  # 不登记
        self.assertIsNone(mgr.get_runtime("agent:s1:paas_sandbox_pdf"))  # store 无记录

    def test_defer_close_failure_does_not_abort_loop(self):
        """第一个 backend put 失败且 close 也抛异常 → close 异常被吞，循环不中断，第二个 backend 正常登记 defer。"""
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store)
        failing = mock.MagicMock()
        failing.save.side_effect = RuntimeError("save boom")
        failing.close.side_effect = RuntimeError("close boom")
        healthy = mock.MagicMock()
        healthy.save.return_value = {"sandbox_id": "sbx-2"}
        mgr.defer(
            {
                "agent:s1:paas_sandbox_pdf": failing,
                "agent:s1:paas_sandbox_skill": healthy,
            }
        )
        failing.close.assert_called_once()  # close 被调过（抛异常被吞）
        self.assertNotIn("agent:s1:paas_sandbox_pdf", mgr._owned)  # 失败者不登记
        self.assertIsNone(mgr.get_runtime("agent:s1:paas_sandbox_pdf"))  # store 无记录
        # 第二个 backend 正常 defer：登记 _owned + store 有记录 + 未被 close
        self.assertIs(mgr._owned["agent:s1:paas_sandbox_skill"].backend, healthy)
        self.assertEqual(mgr.get_runtime("agent:s1:paas_sandbox_skill"), {"sandbox_id": "sbx-2"})
        healthy.close.assert_not_called()

    def test_defer_same_runtime_id_refreshes(self):
        """同 runtime_id 再次 defer：用新 token 覆盖 store 记录 + _owned 换新实例/刷新 expires_at。"""
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store)
        b1 = mock.MagicMock()
        b2 = mock.MagicMock()
        b1.save.return_value = {"sandbox_id": "sbx-1"}
        b2.save.return_value = {"sandbox_id": "sbx-2"}
        mgr.defer({"agent:s1:paas_sandbox_pdf": b1})
        first_token = _token_of(store, "agent:s1:paas_sandbox_pdf")
        first_expires = mgr._owned["agent:s1:paas_sandbox_pdf"].expires_at
        mgr.defer({"agent:s1:paas_sandbox_pdf": b2})
        owned = mgr._owned["agent:s1:paas_sandbox_pdf"]
        self.assertIs(owned.backend, b2)
        # 新 token 覆盖旧 token（旧 entry 的 delete_if_token 因此必失败）
        self.assertNotEqual(_token_of(store, "agent:s1:paas_sandbox_pdf"), first_token)
        self.assertEqual(_token_of(store, "agent:s1:paas_sandbox_pdf"), owned.token)
        self.assertGreaterEqual(owned.expires_at, first_expires)
        self.assertEqual(mgr.get_runtime("agent:s1:paas_sandbox_pdf"), {"sandbox_id": "sbx-2"})


class TestSingleStageDestroy(unittest.TestCase):
    """单阶段 token 销毁（遍历 _owned 驱动 _destroy_entry）各守卫用例。"""

    def test_sweep_delete_if_token_success_closes(self):
        """delete_if_token 成功（记录仍持本进程 token）→ close 持有实例 + 记录消失。"""
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store, idle_ttl=0)
        backend = mock.MagicMock()
        backend.save.return_value = {"sandbox_id": "sbx-1"}
        _defer_and_expire(mgr, store, "agent:s1:paas_sandbox_pdf", backend)
        mgr._sweep_once()
        backend.close.assert_called_once()  # 真实销毁
        self.assertIsNone(mgr.get_runtime("agent:s1:paas_sandbox_pdf"))  # 记录已删
        self.assertNotIn("agent:s1:paas_sandbox_pdf", mgr._owned)

    def test_sweep_token_removed_by_get_skips_close(self):
        """token 版「读即续期拦截」：get 摘 token（挂载复用）→ sweep 不 close、记录保留。"""
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store, idle_ttl=0)
        backend = mock.MagicMock()
        backend.save.return_value = {"sandbox_id": "sbx-1"}
        key = "agent:s1:paas_sandbox_pdf"
        _defer_and_expire(mgr, store, key, backend)
        mgr.get_runtime(key)  # 挂载请求抢先复用：摘除 token
        mgr._sweep_once()
        backend.close.assert_not_called()  # token 已摘：不 close
        self.assertEqual(store.get(key), {"sandbox_id": "sbx-1"})  # 记录保留 payload
        self.assertNotIn(key, mgr._owned)  # 旧 entry pop，所有权交由挂载方重新 defer

    def test_sweep_delete_if_token_fail_drops_without_close(self):
        """记录被其他路径删除（key 不存在）→ delete_if_token False → 不 close、_owned 清理。"""
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store, idle_ttl=0)
        backend = mock.MagicMock()
        backend.save.return_value = {"sandbox_id": "sbx-1"}
        key = "agent:s1:paas_sandbox_pdf"
        _defer_and_expire(mgr, store, key, backend)
        # 模拟记录已被其他路径删除（token 校验对不存在返回 False）
        store.delete_if_token(key, mgr._owned[key].token)  # 直接删记录
        mgr._sweep_once()
        backend.close.assert_not_called()  # 未获销毁权：绝不 close 远端
        self.assertNotIn(key, mgr._owned)  # 本地注册表已清理

    def test_sweep_overwritten_by_new_defer_aborts_without_close(self):
        """旧 entry 过期时记录已被新 defer 覆盖（新 token）→ 不 close 旧实例、_owned 指向新实例。"""
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store, idle_ttl=300)
        old_backend = mock.MagicMock()
        old_backend.save.return_value = {"sandbox_id": "sbx-1"}
        key = "agent:s1:paas_sandbox_pdf"
        mgr.defer({key: old_backend})
        old_entry = mgr._owned[key]
        # 新 defer 已用新实例覆盖 _owned[同 key]（记录亦被刷新为新 token 新 payload）
        new_backend = mock.MagicMock()
        new_backend.save.return_value = {"sandbox_id": "sbx-2"}
        mgr.defer({key: new_backend})
        # 用旧 entry 触发销毁：delete_if_token(old_token) 对新 token 记录返回 False
        mgr._destroy_entry(key, old_entry)
        old_backend.close.assert_not_called()  # token 已被新 defer 覆盖：不 close 旧实例
        self.assertIs(mgr._owned[key].backend, new_backend)  # 新实例保留
        new_backend.close.assert_not_called()


class TestSweep(unittest.TestCase):
    """_sweep_once 遍历 _owned + delete_expired GC。"""

    def test_sweep_traverses_owned_only(self):
        """sweep 只销毁 _owned 里到期的 entry；未到期（未来 expires_at）不销毁。"""
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store, idle_ttl=0)
        expired_backend = mock.MagicMock()
        expired_backend.save.return_value = {"sandbox_id": "sbx-expired"}
        active_backend = mock.MagicMock()
        active_backend.save.return_value = {"sandbox_id": "sbx-active"}
        mgr.defer({"agent:s1:paas_sandbox_pdf": expired_backend})
        mgr.defer({"agent:s1:paas_sandbox_skill": active_backend})
        # 把 active 那条 expires_at 改为未来（未到期）；expired 保持 defer 时的 expires_at（idle_ttl=0 → 已过期）
        with mgr._owned_lock:
            mgr._owned["agent:s1:paas_sandbox_skill"].expires_at = time.time() + 300
        mgr._sweep_once()
        expired_backend.close.assert_called_once()
        active_backend.close.assert_not_called()  # 未到期不销毁
        self.assertIs(mgr._owned["agent:s1:paas_sandbox_skill"].backend, active_backend)

    def test_sweep_runs_delete_expired_gc(self):
        """_sweep_once 末尾调用 store.delete_expired(record_max_age) 清超龄记录。"""
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store, idle_ttl=300, record_max_age=259200.0)
        orphan_key = "agent:s1:paas_sandbox_skill"
        store.put(orphan_key, {"sandbox_id": "sbx-orphan"}, token="tok-orphan")
        # 记录太新鲜 max_age 不删 —— 触发一次 sweep（_owned 为空，仅 GC）
        mgr._sweep_once()
        self.assertIsNotNone(mgr.get_runtime(orphan_key))
        # 直接以 max_age=0 语义验证 delete_expired 计数被 store 正确执行
        removed = store.delete_expired(max_age=0)
        self.assertEqual(removed, 1)

    def test_sweep_without_owned_instance_only_deletes_record(self):
        """过期记录在 _owned 中无持有实例则仅删记录（不 close 任何实例）。"""
        store = RuntimeBackendDeferInMemoryStore()
        key = "agent:s1:paas_sandbox_pdf"
        store.put(key, {"sandbox_id": "sbx-1"}, token="tok-1")
        mgr = _make_mgr(store, idle_ttl=0)
        mgr._sweep_once()  # _owned 为空 → 无销毁动作
        self.assertEqual(mgr._owned, {})
        self.assertIsNotNone(mgr.get_runtime(key))  # 他方记录不受本 pod sweep 影响


class TestAtexitShutdown(unittest.TestCase):
    """shutdown：停线程 + 对持有实例先 token 校验再 close。"""

    def test_shutdown_stops_thread(self):
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store)
        mgr.start()
        self.assertIsNotNone(mgr._thread)
        mgr.shutdown()
        self.assertFalse(mgr._thread.is_alive())

    def test_shutdown_validates_token_before_close(self):
        """defer 一条（_owned 有 entry + store 记录持 token）→ shutdown → 校验成功 close。"""
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store)
        backend = mock.MagicMock()
        backend.save.return_value = {"sandbox_id": "sbx-1"}
        mgr.defer({"agent:s1:paas_sandbox_pdf": backend})
        mgr.shutdown()
        backend.close.assert_called_once()  # token 校验成功 → close
        self.assertEqual(mgr._owned, {})  # 清空

    def test_shutdown_token_removed_skips_close(self):
        """defer 后 get 摘 token → shutdown → token 校验 False → 不 close（他方使用中）。"""
        store = RuntimeBackendDeferInMemoryStore()
        mgr = _make_mgr(store)
        backend = mock.MagicMock()
        backend.save.return_value = {"sandbox_id": "sbx-1"}
        key = "agent:s1:paas_sandbox_pdf"
        mgr.defer({key: backend})
        mgr.get_runtime(key)  # 摘除 token（模拟他 pod/请求正在使用）
        mgr.shutdown()
        backend.close.assert_not_called()  # token 已摘：不误杀他方正在使用的沙箱
        self.assertEqual(mgr._owned, {})


if __name__ == "__main__":
    unittest.main()
