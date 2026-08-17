# -*- coding: utf-8 -*-
"""沙箱延迟销毁（token 化）—— 内存版 store + 所有权接管（defer）/ 挂载查询 / 单阶段 token 销毁 sweep。

本模块提供：
- ``RuntimeBackendDeferInMemoryStore``：``RuntimeBackendDeferStore``
    抽象契约见``types`` 模块，4 原语 get/put/delete_if_token/delete_expired）的内存实现
- ``RuntimeBackendDeferManager``：纯策略层，配合 resolver 的「先构造再挂载 + close 移交所有权」流程
    不接触 store 内部 token 语义（payload/token/last_access_at 完全封装在 store 4 原语内），只关心 TTL/自有实例的 close；
- ``default_runtime_backend_defer_manager``：进程级默认单例（InMemory store，start 幂等），供 chat 装配层直接取用实现跨请求的会话级复用/延迟销毁。

分层：
- store 4 原语（get/put/delete_if_token/delete_expired）
    承载记录 schema（含 token） 与并发控制（get 摘 token 与 delete_if_token 比较删除原子串行）；
- DeferManager 维护自有 ``_owned`` 注册表（``_OwnedBackend`` dataclass 承载 backend + token + expires_at），
    defer 用 uuid4() 生成 token 传入 store.put； sweep 遍历 ``_owned`` 驱动单阶段 token 销毁，周期末尾调用 ``store.delete_expired`` 做超 max_age 记录的 GC

token 语义正确性论证：
- ``get``（有请求挂载复用沙箱）先行动作会原子摘除记录内 token，此后任何旧 entry 的 ``delete_if_token`` 必失败（token 已摘 / 已被新 put 覆盖）
- ``shutdown`` 也先 token 校验再 close，为将来多 pod 分布式 store 提供安全销毁语义（不误杀其他 pod 正在使用的沙箱）。

流程：
- ``defer``：resolver close 时把本请求经手的 backend 移交到本管理器 —— 生成 token = uuid4().hex，save() 导出 payload 经 store.put(runtime_id, payload, token)
  登记记录（供后续请求挂载复用），并保留实例强引用 + token + expires_at；
  store.put/save 失败时立即 close 该 backend 销毁（close 异常自吞记 warning 不中断循环），且不登记 _owned（token 从未落地，登记只会留死 entry）
- ``get_runtime``：原沙箱未被销毁时返回挂载 payload（store.get 纯透传，命中即摘 token 续期）；
- sweep 线程（daemon）周期遍历自有 ``_owned``，对过期的 entry 单阶段销毁
  （delete_if_token 原子校验 → close 持有实例 → pop-if-same 清理本地注册表）；
  ``atexit shutdown`` 停线程并对持有实例先 token 校验再 close。
"""

from __future__ import annotations

import atexit
import dataclasses
import logging
import threading
import time
import uuid

from aidev_agent.config import settings

from .types import RuntimeBackend

logger = logging.getLogger(__name__)


class RuntimeBackendDeferInMemoryStore:
    """内存版 RuntimeBackendDeferStore —— 用于本地开发与单测模拟多 pod 共享存储，作为默认实现
    生产环境为单 pod 单进程时也可以使用本类，如果多进程使用本类，pod 之间不会互相影响，此时退化 runtime 没有 defer 的情况

    记录结构：``_records[key] = {"payload": dict, "token": str | None, "last_access_at": float}``。
    用 ``threading.Lock`` 保证 ``get`` 的摘 token 与 ``delete_if_token`` 的比较删除在 store 内部串行（原子性硬契约）。
    ``get`` 返回 payload 本身而非整个记录。不存 pod 归属字段（sweep 遍历 DeferManager 自有注册表，非按 pod 扫描共享存储）。

    若需跨进程共享（上 MySQL / django cache），写入方需额外在 payload 中带可序列化
    兜底字段（如 ``backend_type`` 字符串或 import_path），load 前先经类引用/导入路径
    恢复。本内存实现以最小改动满足单测为准，不额外加序列化兜底字段。
    """

    def __init__(self) -> None:
        self._records: dict[str, dict] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> dict | None:
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return None
            # 原子摘除 token + 刷新 last_access_at（写回新记录），与 delete_if_token
            # 的比较删除在 store 内部串行 —— 摘 token 后旧 entry 永远无法删除本记录
            record = dict(record)
            record["token"] = None
            record["last_access_at"] = time.time()
            self._records[key] = record
            return dict(record.get("payload") or {})

    def put(self, key: str, payload: dict, token: str) -> None:
        with self._lock:
            self._records[key] = {
                "payload": dict(payload),
                "token": token,
                "last_access_at": time.time(),
            }

    def delete_if_token(self, key: str, token: str) -> bool:
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return False
            if record.get("token") != token:
                return False
            self._records.pop(key, None)
            return True

    def delete_expired(self, max_age: float) -> int:
        with self._lock:
            now = time.time()
            expired_keys = [k for k, r in self._records.items() if now - r.get("last_access_at", 0) > max_age]
            for k in expired_keys:
                self._records.pop(k, None)
            return len(expired_keys)


@dataclasses.dataclass
class _OwnedBackend:
    """DeferManager 自有实例注册表条目 —— backend 实例 + 本进程曾持 token + 计划销毁时刻。"""

    backend: RuntimeBackend
    token: str  # 本进程 defer 时生成的 token（经 store.put 写入记录），供 sweep/shutdown 校验
    expires_at: float  # defer 时 = time.time() + idle_ttl；同 runtime_id 再次 defer 覆盖刷新


class RuntimeBackendDeferManager:
    """沙箱延迟销毁管理器（token 化）—— 纯策略层（所有权接管 / 挂载查询 / 单阶段 token 销毁）。"""

    def __init__(
        self,
        store,
        *,
        idle_ttl: int,
        sweep_interval: int,
        record_max_age: float,
    ) -> None:
        self._store = store
        self._idle_ttl = idle_ttl
        self._sweep_interval = sweep_interval
        self._record_max_age = record_max_age
        # defer 接管的 backend（runtime_id → 实例 + token + 过期时刻），TTL 到期销毁 / 进程退出时 close
        self._owned: dict[str, _OwnedBackend] = {}
        self._owned_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._atexit_registered = False

    def defer(self, backends: dict[str, RuntimeBackend]) -> None:
        """接管 backend 所有权（延迟销毁，resolver close 时调用）。

        对每个 runtime_id：
        - ``token = uuid4().hex`` 由本管理器生成（调用方生成后传入 store.put，store 保持哑存储）；
        - ``backend.save()`` 导出挂载 payload，经 ``store.put(runtime_id, payload, token)`` 登记/覆盖记录
            lazy 未创建的沙箱导出 ``{}``，照常登记保持记录新鲜度；同 runtime_id 再次 defer 用新 token 覆盖，旧 token 失效
        - ``_owned`` 登记实例 + token + expires_at = now + idle_ttl
            同 runtime_id 再次 defer 覆盖刷新 expires_at
        - 异常分支：``store.put``（含 ``backend.save()``，同一 try 块）失败 → 记 warning + 立即
            ``backend.close()`` 真实销毁远端（close 异常自吞记 warning，不中断循环）+
            不登记 _owned（token 从未写入 store，登记只会留死 entry，且后续 delete_if_token 校验必然 False 无法销毁）

        Args:
            backends: runtime_id → backend 实例（resolver 经 compose_runtime_id 组合）。
        """
        for runtime_id, backend in backends.items():
            token = uuid.uuid4().hex
            try:
                self._store.put(runtime_id, backend.save(), token)
            except Exception:  # noqa: BLE001
                # put 失败：记录从未落地，不可能有人挂载/复用，本进程持唯一引用。
                # 立即 close 真实销毁远端（自吞异常，避免中断循环影响其余 backends 的 defer）。
                logger.warning("defer: store.put(%s) 失败，立即销毁该 backend", runtime_id, exc_info=True)
                try:
                    backend.close()
                except Exception:  # noqa: BLE001
                    logger.warning("defer: close %s 失败（store.put 失败后）", runtime_id, exc_info=True)
                continue  # 不登记 _owned —— token 从未写入 store，登记只会留死 entry，且后续 delete_if_token 校验永远失败无法销毁
            with self._owned_lock:
                self._owned[runtime_id] = _OwnedBackend(
                    backend=backend, token=token, expires_at=time.time() + self._idle_ttl
                )
            logger.debug("sandbox %s 所有权移交 DeferManager（延迟销毁）", runtime_id)

    def get_runtime(self, runtime_id: str) -> dict | None:
        """查询原沙箱挂载 payload（纯透传 store.get，命中即摘 token 续期）。

        token 语义：``get`` 意味着有 Agent 复用该沙箱 —— store 内**原子摘除记录内
        token**（置 None）+ 刷新 last_access_at。token 被摘除后，任何旧 entry 的 ``delete_if_token`` 必失败（token 已摘 / 已被新 put 覆盖）
        旧记录永远无法被 close 销毁 —— 彻底关闭「turn 超 idle_ttl 被误杀」窗口，无需心跳
        记录不存在返回 None 且不创建记录。

        Args:
            runtime_id: 沙箱生命周期标识（resolver ``compose_runtime_id`` 产出）。

        Returns:
            记录的挂载 payload（``backend.save()`` 产出）。payload 为 ``{}``
            表示原沙箱从未真正拉起过（``backend.load({})`` 应为 no-op）；记录不存在时返回 None。
        """
        return self._store.get(runtime_id)

    def _pop_owned_if_same(self, key: str, entry: _OwnedBackend) -> bool:
        """本地注册表卫生：仅当 ``_owned[key] is entry`` 时移除。

        身份比较防止弹掉并发 defer 刚登记的新 entry（旧 entry 被覆盖时本方法是 no-op，旧 backend 的回收由接管方负责）。
        每个销毁出口统一调用，防止 sweep 每周期对同一 entry 无限重试。
        """
        with self._owned_lock:
            if self._owned.get(key) is entry:
                self._owned.pop(key, None)
                return True
            return False

    def _destroy_entry(self, key: str, entry: _OwnedBackend) -> None:
        """单阶段 token 销毁单条自有 entry（delete_if_token 原子校验 → close → pop）。

        ``store.delete_if_token(key, entry.token)``：
        - 返回 True（记录仍持本进程 token → 无人挂载、未被新 defer 覆盖）→ close 持有实例（真实销毁远端，异常 warning 包裹）→ pop-if-same 清理本地注册表；
        - 返回 False（token 被摘 = 有请求挂载中，或被新 defer 覆盖 = 新 entry 接管）
          → **不 close**，仅 pop-if-same 回收本地旧 entry（远端由挂载方结束时的
          defer / 新 entry 到期 sweep 接管）。
        """
        try:
            if not self._store.delete_if_token(key, entry.token):
                # 未获销毁权：token 已摘（有请求挂载中）/ 已被新 put 覆盖 / 记录不存在。
                # 绝不 close 远端 —— 可能是其他 pod / 挂载方正在使用同一沙箱
                logger.info("sandbox %s token 校验失败，不销毁（挂载中/已被接管）", key)
                self._pop_owned_if_same(key, entry)
                return
            try:
                entry.backend.close()
                logger.info("sandbox %s 持有实例已 close（远端真实销毁）", key)
            except Exception:  # noqa: BLE001
                logger.warning("sandbox %s 持有实例 close 失败", key, exc_info=True)
            self._pop_owned_if_same(key, entry)
        except Exception:  # noqa: BLE001
            logger.warning("sweep 处理 %s 失败", key, exc_info=True)

    def _sweep_once(self) -> None:
        """遍历自有 _owned 驱动单阶段 token 销毁；周期末尾 delete_expired 做 GC。"""
        if self._store is None:
            return
        with self._owned_lock:
            snapshot = list(self._owned.items())
        now = time.time()
        for key, entry in snapshot:
            if now <= entry.expires_at:
                continue
            self._destroy_entry(key, entry)
        try:
            removed = self._store.delete_expired(self._record_max_age)
            if removed:
                logger.info("sweep GC: 删除 %s 条超 max_age 的过期记录", removed)
        except Exception:  # noqa: BLE001
            logger.warning("sweep delete_expired GC 失败", exc_info=True)

    def _sweep_loop(self) -> None:
        while not self._stop_event.wait(self._sweep_interval):
            self._sweep_once()

    def start(self) -> None:
        """懒启动 sweep 线程（daemon=True，幂等）。"""
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._sweep_loop,
                name="sandbox-lifecycle-sweep",
                daemon=True,
            )
            self._thread.start()
            if not self._atexit_registered:
                atexit.register(self.shutdown)
                self._atexit_registered = True

    def shutdown(self) -> None:
        """进程退出兜底：停 sweep 线程并对持有实例先 token 校验再 close（真实销毁远端）。

        先 ``store.delete_if_token(runtime_id, owned.token)``：
            返回 True 记录仍持本进程 token → 无人挂载、未被新 defer 覆盖才 close 持有实例
            返回 False（token 被摘 = 其他 pod / 请求在使用）则**不 close**，仅丢弃本地引用
        对将来多 pod 分布式 store 更安全 —— 避免误杀其他 pod 正在使用的沙箱。
        InMemory store 的记录随进程消亡；无持有实例的记录由其他 pod 的 sweep 按 TTL 清理（远端由平台 TTL 兜底）。
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        with self._owned_lock:
            items = list(self._owned.items())
            self._owned.clear()
        for runtime_id, owned in items:
            try:
                if not self._store.delete_if_token(runtime_id, owned.token):
                    logger.info("shutdown: %s token 校验失败，不 close（他方使用中）", runtime_id)
                    continue
                owned.backend.close()
            except Exception:  # noqa: BLE001
                logger.warning("shutdown: close %s 失败", runtime_id, exc_info=True)


# ---- 进程级默认单例（决策 1 + CR6）----
# 每个 pod 一个进程级 InMemory store + DeferManager，跨请求共享以实现会话级
# 复用/延迟销毁。start() 幂等：daemon sweep 线程与 atexit shutdown 随模块导入
# 注册（sweep 空转开销可忽略）。将来接入真实分布式 store 时，替换本单例的
# store 构造来源即可（换成 Redis/MySQL 实现的 RuntimeBackendDeferStore）。
default_runtime_backend_defer_manager = RuntimeBackendDeferManager(
    RuntimeBackendDeferInMemoryStore(),
    idle_ttl=settings.BKAI_RUNTIME_SANDBOX_IDLE_TTL,
    sweep_interval=settings.BKAI_RUNTIME_SANDBOX_SWEEP_INTERVAL,
    record_max_age=settings.BKAI_RUNTIME_SANDBOX_RECORD_MAX_AGE,
)
default_runtime_backend_defer_manager.start()


__all__ = ["RuntimeBackendDeferInMemoryStore", "RuntimeBackendDeferManager", "default_runtime_backend_defer_manager"]
