# -*- coding: utf-8 -*-
"""沙箱复用端到端集成测试（先构造再挂载 + close 移交所有权流程，4 原语 token 语义）。

覆盖完整复用链路：请求 1 全新创建（lazy）→ resolver.close() 移交所有权给
RuntimeBackendDeferManager（defer：store.put 登记持 token + 持有实例）→ 请求 2
get_runtime 命中（store.get 摘 token，仍返回 payload）→ backend.load 实例方法挂载复用
→ close 再次移交续期（新 token put）；TTL 到期 sweep 遍历 _owned close 持有实例（真实
销毁）+ delete_expired GC；记录已销毁（store 无记录）走全新创建；close defer 用新 token
续期；安全不变量（agent/session 缺失 → 延迟销毁策略关闭，close 立即销毁）；多 pod
并发 delete_if_token 竞态（只有一个成功）。

token 语义封装在 store 内，测试不 import STATE_*、不 backdate last_access_at（让某
_owned entry 到期改为 defer_manager._owned[key].expires_at 为过去即可，不 mock time.sleep）。
"""

from __future__ import annotations

import threading
import time
import unittest
from unittest import mock

from aidev_agent.core.tools.runtime_tools.defer_manager import (
    RuntimeBackendDeferInMemoryStore,
    RuntimeBackendDeferManager,
)
from aidev_agent.core.tools.runtime_tools.provider import RuntimeBackendResolver
from aidev_agent.core.tools.runtime_tools.types import RuntimeBackend


def _make_mgr(store, **overrides):
    kwargs = {
        "store": store,
        "idle_ttl": 300,
        "sweep_interval": 60,
        "record_max_age": 259200.0,
    }
    kwargs.update(overrides)
    return RuntimeBackendDeferManager(**kwargs)


def _make_fake_resolver(**kwargs):
    """构造 resolver 并预注册 _FakeBackend 到 runtime 类型注册表（fake）。"""
    resolver = RuntimeBackendResolver(**kwargs)
    resolver.register_runtime_cls("fake", _FakeBackend)
    return resolver


def _token_of(store, key):
    """取 store 记录内当前 token（None 表示已被摘除/无记录）。"""
    record = store._records.get(key)
    return record.get("token") if record else None


def _payload_of(store, key):
    """取 store 记录内 payload（不消费 token）。"""
    record = store._records.get(key)
    return dict(record["payload"]) if record else None


class _FakeBackend(RuntimeBackend):
    """测试用 fake backend：lazy 语义 —— 构造不建沙箱，save 在未创建时导出 {}。"""

    def __init__(self, *, sandbox_id: str | None = None) -> None:
        self.sandbox_id = sandbox_id  # None = 远端沙箱未创建（lazy）
        self.created = False
        self.kill_count = 0
        self.close_count = 0

    def create(self, sandbox_id: str = "sbx-new") -> str:
        """模拟首次使用触发远端沙箱创建。"""
        self.sandbox_id = sandbox_id
        self.created = True
        return self.sandbox_id

    def save(self) -> dict:
        if self.sandbox_id is None:
            return {}  # 未创建沙箱，默认导出 {}（不抛异常）
        return {"sandbox_id": self.sandbox_id}

    def load(self, payload: dict) -> None:
        """实例方法挂载：指向既有沙箱；payload 为 {} 时 no-op（不创建沙箱）。"""
        sandbox_id = payload.get("sandbox_id")
        if not sandbox_id:
            return
        self.sandbox_id = sandbox_id
        self.created = False

    def kill(self) -> None:
        self.kill_count += 1

    def close(self) -> None:  # type: ignore[override]
        self.close_count += 1
        self.kill()


class TestSandboxReuseIntegration(unittest.TestCase):
    """沙箱复用端到端集成测试（先构造再挂载 + close 移交所有权）。"""

    def test_reuse_chain_create_close_defer_reattach(self):
        """完整链路：全新创建 → close 移交（defer 持 token）→ 下请求挂载复用 → close 续期。"""
        store = RuntimeBackendDeferInMemoryStore()
        defer_manager = _make_mgr(store)
        defer_manager.start()
        resolver = _make_fake_resolver(
            default_runtime="local", defer_manager=defer_manager, agent_code="agent", session_code="s1"
        )
        runtime_name = "paas_sandbox_pdf"
        runtime_id = resolver.compose_runtime_id(runtime_name)
        self.assertEqual(runtime_id, "agent:s1:paas_sandbox_pdf")

        # 请求 1：全新创建（lazy，不写 store）
        first = resolver.get_or_create_backend(runtime_name, "fake", {})
        self.assertIsNone(first.sandbox_id)  # 尚无远端沙箱
        self.assertIsNone(store.get(runtime_id))  # 未写 store
        first.create("sbx-1")
        # 请求 1 结束：close 移交所有权（defer：store.put 持 token + 持有实例，不销毁）
        resolver.close()
        self.assertIsNotNone(_token_of(store, runtime_id))  # defer 已持 token 登记
        self.assertEqual(store.get(runtime_id), {"sandbox_id": "sbx-1"})  # get 摘 token 返回 payload
        self.assertEqual(first.close_count, 0)  # defer 不销毁
        self.assertIs(defer_manager._owned[runtime_id].backend, first)  # 所有权已移交

        # 请求 2（新 resolver，同 agent/session）：get_runtime 命中（摘 token）→ load 挂载
        resolver2 = _make_fake_resolver(
            default_runtime="local", defer_manager=defer_manager, agent_code="agent", session_code="s1"
        )
        second = resolver2.get_or_create_backend(runtime_name, "fake", {})
        self.assertIsNot(second, first)  # 全新实例
        self.assertEqual(second.sandbox_id, "sbx-1")  # 挂载到原沙箱
        self.assertFalse(second.created)  # 跳过创建
        self.assertIs(resolver2._backends[runtime_name], second)  # 注册到模型可见路由名
        # get_runtime（挂载）已摘除旧 token —— 旧 entry 无法再删除本记录
        self.assertIsNone(_token_of(store, runtime_id))
        # 请求 2 结束：close 再次移交（用新 token put 续期）；payload 经记录直读核对
        # （不经 store.get —— 以免消费 token 导致 shutdown 无法校验 close）
        resolver2.close()
        self.assertEqual(_payload_of(store, runtime_id), {"sandbox_id": "sbx-1"})
        self.assertIsNotNone(_token_of(store, runtime_id))  # 新 token 已登记
        self.assertIs(defer_manager._owned[runtime_id].backend, second)
        defer_manager.shutdown()  # 进程退出兜底：token 校验成功 close 持有实例
        self.assertEqual(second.close_count, 1)

    def test_deferred_disabled_close_destroys_immediately(self):
        """agent/session 缺失 → 延迟销毁策略关闭，close 立即销毁、不写 store。"""
        store = RuntimeBackendDeferInMemoryStore()
        defer_manager = _make_mgr(store)
        resolver = _make_fake_resolver(default_runtime="local", defer_manager=defer_manager, agent_code="agent")
        runtime_id = resolver.compose_runtime_id("paas_sandbox_pdf")
        self.assertEqual(runtime_id, "paas_sandbox_pdf")  # scoping 缺失回退原名

        backend = resolver.get_or_create_backend("paas_sandbox_pdf", "fake", {})
        self.assertIsNone(backend.sandbox_id)  # 全新 lazy 实例
        self.assertIsNone(store.get(runtime_id))  # 不写 store
        resolver.close()  # close 立即销毁
        self.assertEqual(backend.close_count, 1)
        self.assertEqual(defer_manager._owned, {})  # 无所有权移交

    def test_reattach_refreshes_last_access_at_close(self):
        """close 移交时 save() → store.put 覆盖续期（payload 更新，持新 token）。"""
        store = RuntimeBackendDeferInMemoryStore()
        defer_manager = _make_mgr(store)
        defer_manager.start()
        resolver = _make_fake_resolver(
            default_runtime="local", defer_manager=defer_manager, agent_code="agent", session_code="s1"
        )
        runtime_name = "paas_sandbox_pdf"
        runtime_id = resolver.compose_runtime_id(runtime_name)
        store.put(runtime_id, {"sandbox_id": "sbx-1"}, token="tok-pre")

        backend = resolver.get_or_create_backend(runtime_name, "fake", {})
        self.assertEqual(backend.sandbox_id, "sbx-1")  # 挂载到原沙箱
        backend.create("sbx-2")  # 本次使用新沙箱
        resolver.close()  # defer：store.put 覆盖续期（新 token）
        # payload 经记录直读核对（不经 store.get —— 以免消费 token 使 shutdown 无法 close）
        self.assertEqual(_payload_of(store, runtime_id), {"sandbox_id": "sbx-2"})
        self.assertIs(defer_manager._owned[runtime_id].backend, backend)
        defer_manager.shutdown()
        self.assertEqual(backend.close_count, 1)  # shutdown 兜底 close

    def test_destroyed_record_not_reattached_creates_fresh(self):
        """记录已销毁（store 无该 key 记录）→ 不挂载，走全新创建。

        token 语义版「EXPIRING 不挂载」：已销毁沙箱 = delete_if_token 成功删除记录
        （或从未登记）—— store 无记录，get_runtime 返回 None → 全新 lazy 实例；close
        移交后用新 token put 登记。
        """
        store = RuntimeBackendDeferInMemoryStore()
        defer_manager = _make_mgr(store)
        defer_manager.start()
        resolver = _make_fake_resolver(
            default_runtime="local", defer_manager=defer_manager, agent_code="agent", session_code="s1"
        )
        runtime_name = "paas_sandbox_pdf"
        runtime_id = resolver.compose_runtime_id(runtime_name)
        # 旧沙箱已销毁：无记录（旧记录 token 已被摘除且 payload 已随销毁移除）
        self.assertIsNone(store.get(runtime_id))

        backend = resolver.get_or_create_backend(runtime_name, "fake", {})
        self.assertIsNone(backend.sandbox_id)  # 全新 lazy 实例，未挂载旧沙箱
        backend.create("sbx-new")  # 本次请求实际创建新沙箱
        resolver.close()  # defer：store.put 登记持新 token
        # payload 经记录直读核对（不经 store.get —— 以免消费 token 使 shutdown 无法 close）
        self.assertEqual(_payload_of(store, runtime_id), {"sandbox_id": "sbx-new"})
        self.assertIsNotNone(_token_of(store, runtime_id))
        defer_manager.shutdown()
        self.assertEqual(backend.close_count, 1)

    def test_close_defers_empty_payload_for_unused(self):
        """本次请求未使用（lazy 未创建）→ save 导出 {}，照常登记空 payload。"""
        store = RuntimeBackendDeferInMemoryStore()
        defer_manager = _make_mgr(store)
        defer_manager.start()
        resolver = _make_fake_resolver(
            default_runtime="local", defer_manager=defer_manager, agent_code="agent", session_code="s1"
        )
        runtime_name = "paas_sandbox_pdf"
        runtime_id = resolver.compose_runtime_id(runtime_name)

        resolver.get_or_create_backend(runtime_name, "fake", {})
        resolver.close()  # defer：save() {} 照常登记
        self.assertEqual(store.get(runtime_id), {})
        # 下请求 get_runtime 返回 {}，load({}) no-op，backend 保持 lazy
        self.assertEqual(defer_manager.get_runtime(runtime_id), {})
        resolver2 = _make_fake_resolver(
            default_runtime="local", defer_manager=defer_manager, agent_code="agent", session_code="s1"
        )
        second = resolver2.get_or_create_backend(runtime_name, "fake", {})
        self.assertIsNone(second.sandbox_id)  # 未创建沙箱
        defer_manager.shutdown()
        resolver.close()
        resolver2.close()

    def test_sweep_destroys_owned_instance(self):
        """TTL 到期：sweep 遍历 _owned delete_if_token 校验成功后 close 持有实例（真实销毁）+ 删记录。"""
        store = RuntimeBackendDeferInMemoryStore()
        defer_manager = _make_mgr(store, idle_ttl=0)
        defer_manager.start()
        resolver = _make_fake_resolver(
            default_runtime="local", defer_manager=defer_manager, agent_code="agent", session_code="s1"
        )
        runtime_name = "paas_sandbox_pdf"
        runtime_id = resolver.compose_runtime_id(runtime_name)
        backend = resolver.get_or_create_backend(runtime_name, "fake", {})
        backend.create("sbx-1")
        resolver.close()  # 移交所有权
        self.assertIs(defer_manager._owned[runtime_id].backend, backend)
        # 让该 entry 到期（改 defer_manager._owned expires_at 为过去，不触碰 store）
        with defer_manager._owned_lock:
            defer_manager._owned[runtime_id].expires_at = time.time() - 1
        defer_manager._sweep_once()
        self.assertEqual(backend.close_count, 1)  # 真实销毁
        self.assertIsNone(store.get(runtime_id))  # 记录已删
        self.assertNotIn(runtime_id, defer_manager._owned)
        defer_manager.shutdown()

    def test_sweep_only_touches_owned_expired(self):
        """sweep 只销毁 defer_manager 自有 _owned 中已到期的 entry，不碰其他共享记录。"""
        store = RuntimeBackendDeferInMemoryStore()
        defer_manager = _make_mgr(store, idle_ttl=0)
        # 其他 pod/会话写入的无主共享记录（defer_manager._owned 无条目）——不受本 pod sweep 影响
        orphan_id = "agent:s1:paas_sandbox_skill"
        store.put(orphan_id, {"sandbox_id": "sbx-orphan"}, token="tok-orphan")
        # 本 pod defer 一条
        backend = mock.MagicMock()
        backend.save.return_value = {"sandbox_id": "sbx-owned"}
        runtime_id = "agent:s1:paas_sandbox_pdf"
        defer_manager.defer({runtime_id: backend})
        with defer_manager._owned_lock:
            defer_manager._owned[runtime_id].expires_at = time.time() - 1
        defer_manager._sweep_once()
        backend.close.assert_called_once()
        self.assertIsNone(store.get(runtime_id))  # 自有到期记录被销毁删记录
        self.assertEqual(store.get(orphan_id), {"sandbox_id": "sbx-orphan"})  # 他方记录不动

    def test_sweep_gc_removes_superaged_records(self):
        """_sweep_once 末尾 delete_expired(record_max_age) 清超龄无主记录。"""
        store = RuntimeBackendDeferInMemoryStore()
        defer_manager = _make_mgr(store, idle_ttl=300, record_max_age=259200.0)
        orphan_id = "agent:s1:paas_sandbox_skill"
        store.put(orphan_id, {"sandbox_id": "sbx-orphan"}, token="tok-orphan")
        # 无自有条目，sweep 仅执行 delete_expired GC；记录太新鲜(max_age 3 天)不被删
        defer_manager._sweep_once()
        self.assertEqual(store.get(orphan_id), {"sandbox_id": "sbx-orphan"})
        # 直测 delete_expired 超龄删除语义（max_age=0 全删）
        removed = store.delete_expired(max_age=0)
        self.assertEqual(removed, 1)

    def test_register_runtime_conflict_rules(self):
        """同名同实例幂等返回；同名异实例抛 ValueError。"""
        resolver = _make_fake_resolver(default_runtime="local")
        backend = _FakeBackend()
        resolver.register_runtime("local_x", backend)
        resolver.register_runtime("local_x", backend)  # 同实例幂等
        self.assertIs(resolver._backends["local_x"], backend)
        with self.assertRaises(ValueError):
            resolver.register_runtime("local_x", _FakeBackend())  # 同名异实例
        resolver.close()

    def test_concurrent_pod_race_only_one_wins(self):
        """多 pod 竞态：并发 delete_if_token(key, same_token) 恰好 1 个成功、其余失败。"""
        store = RuntimeBackendDeferInMemoryStore()
        key = "agent:s1:paas_sandbox_pdf"
        store.put(key, {"sandbox_id": "sbx-1"}, token="tok-1")
        n_threads = 8
        barrier = threading.Barrier(n_threads)
        success: list[int] = []
        lock = threading.Lock()

        def try_delete():
            barrier.wait()
            ok = store.delete_if_token(key, "tok-1")
            if ok:
                with lock:
                    success.append(1)

        threads = [threading.Thread(target=try_delete) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(success), 1)  # 只有一个 delete_if_token 成功
        self.assertIsNone(store.get(key))  # 删除后记录不存在

    def test_sweep_skips_close_when_token_consumed_by_mount(self):
        """集成 CR：请求挂载（get 摘 token）后旧 entry 到期 sweep → 不误杀正在复用沙箱。"""
        store = RuntimeBackendDeferInMemoryStore()
        defer_manager = _make_mgr(store, idle_ttl=0)
        defer_manager.start()
        resolver = _make_fake_resolver(
            default_runtime="local", defer_manager=defer_manager, agent_code="agent", session_code="s1"
        )
        runtime_name = "paas_sandbox_pdf"
        runtime_id = resolver.compose_runtime_id(runtime_name)
        backend = resolver.get_or_create_backend(runtime_name, "fake", {})
        backend.create("sbx-1")
        resolver.close()  # 请求 1 结束：defer 持 token
        # 请求 2 挂载（get 摘 token）并已开始使用；旧 entry 此刻到期触发 sweep
        defer_manager.get_runtime(runtime_id)
        with defer_manager._owned_lock:
            defer_manager._owned[runtime_id].expires_at = time.time() - 1
        defer_manager._sweep_once()
        self.assertEqual(backend.close_count, 0)  # token 已摘：不误杀挂载中的沙箱
        self.assertEqual(store.get(runtime_id), {"sandbox_id": "sbx-1"})  # 记录保留
        self.assertNotIn(runtime_id, defer_manager._owned)  # 旧 entry pop，交由挂载方 defer
        defer_manager.shutdown()


if __name__ == "__main__":
    unittest.main()
