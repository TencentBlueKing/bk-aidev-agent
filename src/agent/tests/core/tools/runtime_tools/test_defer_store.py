# -*- coding: utf-8 -*-
"""RuntimeBackendDeferInMemoryStore 单元测试（4 原语 token 化）。

覆盖 get 摘 token（二次 get 仍返回 payload / 不存在 None 且不创建记录）、put
覆盖、delete_if_token 四分支（token 相等删 / token 不符留 / token 已摘留 / 不存在
False）、delete_expired 计数，以及多线程并发 delete_if_token 竞态（模拟多 pod 共享
存储，恰好只有一个成功）。token 语义已封装在 store 内，测试不触碰内部时间戳、
不 backdate last_access_at、不 import STATE_*。
"""

from __future__ import annotations

import threading
import unittest

from aidev_agent.core.tools.runtime_tools.defer_manager import RuntimeBackendDeferInMemoryStore


class TestRuntimeBackendDeferInMemoryStore(unittest.TestCase):
    """RuntimeBackendDeferInMemoryStore 4 原语 token 化语义测试。"""

    def test_get_removes_token_and_returns_payload(self):
        """put 后 get 返回 payload；再 get（token 已 None）仍返回同一 payload。"""
        store = RuntimeBackendDeferInMemoryStore()
        key = "sandbox:session_1:paas_sandbox_skill"
        store.put(key, {"sandbox_id": "sbx-1"}, token="tok-1")
        self.assertEqual(store.get(key), {"sandbox_id": "sbx-1"})
        # 二次 get：token 已摘除为 None，但照常返回 payload（挂载方仍在读）
        self.assertEqual(store.get(key), {"sandbox_id": "sbx-1"})
        self.assertIsNone(store._records[key]["token"])  # token 已被摘除

    def test_get_absent_returns_none_and_no_record_created(self):
        """对不存在的 key get 返回 None，且不创建记录。"""
        store = RuntimeBackendDeferInMemoryStore()
        key = "sandbox:session_1:paas_sandbox_skill"
        self.assertIsNone(store.get(key))
        self.assertEqual(store._records, {})  # get 不创建记录

    def test_put_overwrites_record(self):
        """同 key 连续 put（不同 token/payload）后 get 返回最后一次 payload。"""
        store = RuntimeBackendDeferInMemoryStore()
        key = "sandbox:session_1:paas_sandbox_skill"
        store.put(key, {"sandbox_id": "sbx-1"}, token="tok-1")
        store.put(key, {"sandbox_id": "sbx-2"}, token="tok-2")
        self.assertEqual(store.get(key), {"sandbox_id": "sbx-2"})

    def test_delete_if_token_four_branches(self):
        """delete_if_token：token 相等删 / token 不符留 / token 已摘留 / 不存在 False。"""
        store = RuntimeBackendDeferInMemoryStore()
        key = "sandbox:session_1:paas_sandbox_skill"
        store.put(key, {"sandbox_id": "sbx-1"}, token="tok-1")
        # ① token 相符 → True 且记录消失
        self.assertTrue(store.delete_if_token(key, "tok-1"))
        self.assertIsNone(store.get(key))
        # ② key 不存在 → False
        self.assertFalse(store.delete_if_token(key, "tok-1"))
        # ③ token 不符 → False 且记录保留
        store.put(key, {"sandbox_id": "sbx-2"}, token="tok-2")
        self.assertFalse(store.delete_if_token(key, "wrong-token"))
        self.assertEqual(store.get(key), {"sandbox_id": "sbx-2"})
        # ④ token 已被 get 摘除（None）→ False 且记录保留
        store.put(key, {"sandbox_id": "sbx-3"}, token="tok-3")
        store.get(key)  # 摘除 token
        self.assertFalse(store.delete_if_token(key, "tok-3"))
        self.assertEqual(store.get(key), {"sandbox_id": "sbx-3"})  # 记录保留

    def test_delete_expired_counts(self):
        """delete_expired：max_age=0 删所有（计数正确）；max_age=1e9 不删任何。"""
        store = RuntimeBackendDeferInMemoryStore()
        keys = [f"sandbox:session_{i}:paas_sandbox_skill" for i in range(3)]
        for idx, k in enumerate(keys):
            store.put(k, {"sandbox_id": f"sbx-{idx}"}, token=f"tok-{idx}")
        removed = store.delete_expired(max_age=0)  # 全部过期
        self.assertEqual(removed, 3)
        self.assertEqual(len(store._records), 0)  # 内部记录清空
        # 重新登记后超大 max_age 不删任何
        for k in keys:
            store.put(k, {"sandbox_id": "sbx-new"}, token="tok-new")
        removed = store.delete_expired(max_age=1e9)
        self.assertEqual(removed, 0)
        self.assertEqual(len(store._records), 3)


class TestDeleteIfTokenAtomicity(unittest.TestCase):
    """多线程并发 delete_if_token 竞态测试（模拟多 pod 共享存储）。

    并发对同一 put 记录调 delete_if_token(key, same_token)，恰好 1 个成功、其余失败。
    """

    def test_concurrent_delete_if_token_only_one_wins(self):
        store = RuntimeBackendDeferInMemoryStore()
        key = "sandbox:session_1:paas_sandbox_skill"
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


if __name__ == "__main__":
    unittest.main()
