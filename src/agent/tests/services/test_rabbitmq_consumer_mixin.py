import contextlib
import multiprocessing
import os
import time

import pytest
from aidev_agent.services.messages_handler.base import EOD_CHUNK, ConsumerPreemptedError
from aidev_agent.services.messages_handler.rabbitmq import RabbitMQMessageHandler

# 标记：所有测试均需要 RabbitMQ
pytestmark = pytest.mark.skipif(
    not os.getenv("RABBITMQ_HOST"),
    reason="Live test requires RABBITMQ_HOST",
)


# ==================== Fixtures ====================


@pytest.fixture()
def handler():
    """创建 handler 实例，每个测试重置单例"""
    RabbitMQMessageHandler._instance = None
    h = RabbitMQMessageHandler()
    yield h


@pytest.fixture()
def thread_id(request, handler):
    """为每个测试生成唯一的 thread_id，测试后自动清理"""
    tid = f"test-cm-{request.node.name}-{int(time.time() * 1000) % 100000}"
    yield tid
    with contextlib.suppress(Exception):
        handler.clear(tid)


@pytest.fixture()
def mp_ctx():
    """提供 spawn 上下文用于多进程测试"""
    return multiprocessing.get_context("spawn")


@pytest.fixture()
def env_vars():
    """收集当前进程的 RabbitMQ 环境变量，传递给子进程"""
    keys = ["RABBITMQ_HOST", "RABBITMQ_PORT", "RABBITMQ_USER", "RABBITMQ_PASSWORD", "RABBITMQ_VHOST"]
    return {k: os.environ[k] for k in keys if k in os.environ}


# ==================== 单进程单元测试 ====================


class TestConsumerAcquire:
    """acquire_consumer 核心行为"""

    def test_returns_32char_hex(self, handler, thread_id):
        """返回 32 位十六进制字符串"""
        consumer_id = handler.acquire_consumer(thread_id)
        assert len(consumer_id) == 32
        int(consumer_id, 16)

    def test_consecutive_acquire_returns_unique_ids(self, handler, thread_id):
        """连续 acquire 返回不同 ID，且新 ID 抢占旧 ID"""
        id1 = handler.acquire_consumer(thread_id)
        id2 = handler.acquire_consumer(thread_id)
        assert id1 != id2

        handler.check_consumer(thread_id, id2)
        with pytest.raises(ConsumerPreemptedError):
            handler.check_consumer(thread_id, id1)

    def test_control_queue_keeps_only_latest(self, handler, thread_id):
        """连续 5 次 acquire，控制队列始终只保留最后一个 consumer_id"""
        ids = [handler.acquire_consumer(thread_id) for _ in range(5)]

        handler.check_consumer(thread_id, ids[-1])
        for old_id in ids[:-1]:
            with pytest.raises(ConsumerPreemptedError):
                handler.check_consumer(thread_id, old_id)


class TestConsumerCheck:
    """check_consumer 核心行为"""

    def test_active_consumer_passes(self, handler, thread_id):
        """当前活跃消费者 check 不抛异常"""
        cid = handler.acquire_consumer(thread_id)
        handler.check_consumer(thread_id, cid)

    def test_empty_queue_passes(self, handler, thread_id):
        """控制队列不存在 / 为空时 check 任意 ID 都通过"""
        handler.check_consumer(thread_id, "nonexistent-id")


class TestConsumerRelease:
    """release_consumer 核心行为"""

    def test_normal_release_clears_control_queue(self, handler, thread_id):
        """正常释放后控制队列为空"""
        cid = handler.acquire_consumer(thread_id)
        handler.release_consumer(thread_id, cid)
        handler.check_consumer(thread_id, "any-id-after-release")

    def test_preempted_release_restores_dlq_and_sends_signal(self, handler):
        """被抢占的消费者释放时：恢复 DLQ → 主队列 + 发送退出信号"""
        tid = f"test-dlq-restore-{int(time.time() * 1000) % 100000}"
        try:
            handler.clear(tid)

            for msg in ["m1", "m2", "m3"]:
                handler.put(tid, msg)
            handler.flush(tid)
            assert handler.get_cached_count(tid) == 3

            old_id = handler.acquire_consumer(tid)
            messages = handler.get(tid, timeout=1)
            assert messages == ["m1", "m2", "m3"]
            assert handler._get_dlq_count(tid) == 3
            assert handler.get_cached_count(tid) == 0

            new_id = handler.acquire_consumer(tid)
            handler.release_consumer(tid, old_id)

            assert handler._get_dlq_count(tid) == 0
            assert handler.get_cached_count(tid) == 3

            assert handler.wait_for_previous_consumer(tid, timeout=2.0) is True

            msgs = handler.get(tid, timeout=1)
            assert msgs == ["m1", "m2", "m3"]

            handler.release_consumer(tid, new_id)
            handler.mark_completed(tid)
        finally:
            handler.clear(tid)

    def test_double_release_is_safe(self, handler, thread_id):
        """重复释放不报错"""
        cid = handler.acquire_consumer(thread_id)
        handler.release_consumer(thread_id, cid)
        handler.release_consumer(thread_id, cid)

    def test_rapid_acquire_release_cycle(self, handler, thread_id):
        """10 次快速 acquire/release 不出现状态不一致"""
        for _ in range(10):
            cid = handler.acquire_consumer(thread_id)
            handler.check_consumer(thread_id, cid)
            handler.release_consumer(thread_id, cid)
        handler.check_consumer(thread_id, "any-id")


class TestWaitForPreviousConsumer:
    """wait_for_previous_consumer 核心行为"""

    def test_no_signal_timeout(self, handler, thread_id):
        """没有退出信号时超时返回 False"""
        handler.acquire_consumer(thread_id)
        assert handler.wait_for_previous_consumer(thread_id, timeout=0.5) is False

    def test_queue_not_exist_returns_true(self, handler, thread_id):
        """退出通知队列不存在时立即返回 True"""
        assert handler.wait_for_previous_consumer(thread_id, timeout=0.5) is True


class TestEndToEnd:
    """端到端完整流程"""

    def test_preemption_and_resume(self, handler, thread_id):
        """完整断点续传：写入 → A 消费 → B 抢占 → A release(恢复DLQ+信号) → B 消费"""
        handler.clear(thread_id)
        all_msgs = [f"c_{i}" for i in range(5)] + [EOD_CHUNK]
        for msg in all_msgs:
            handler.put(thread_id, msg)
        handler.flush(thread_id)

        consumer_a = handler.acquire_consumer(thread_id)
        handler.get(thread_id, timeout=1)
        assert handler._get_dlq_count(thread_id) == 6

        consumer_b = handler.acquire_consumer(thread_id)

        with pytest.raises(ConsumerPreemptedError):
            handler.check_consumer(thread_id, consumer_a)

        handler.release_consumer(thread_id, consumer_a)
        assert handler.get_cached_count(thread_id) == 6
        assert handler.wait_for_previous_consumer(thread_id, timeout=2.0) is True

        assert handler.get(thread_id, timeout=1) == all_msgs

        handler.mark_completed(thread_id)
        handler.release_consumer(thread_id, consumer_b)
        assert handler.is_empty(thread_id) is True

    def test_normal_flow_no_preemption(self, handler, thread_id):
        """正常流程：acquire → check → 消费 → mark_completed → release"""
        handler.clear(thread_id)
        for msg in ["d1", "d2", EOD_CHUNK]:
            handler.put(thread_id, msg)
        handler.flush(thread_id)

        cid = handler.acquire_consumer(thread_id)
        handler.check_consumer(thread_id, cid)
        assert handler.get(thread_id, timeout=1) == ["d1", "d2", EOD_CHUNK]

        handler.mark_completed(thread_id)
        handler.release_consumer(thread_id, cid)
        assert handler.is_empty(thread_id) is True


# ==================== 多进程集成测试 ====================
#
# 所有 worker 函数定义在模块顶层，便于 spawn 子进程 pickle。
# 导入语句在函数内部仅限 RabbitMQMessageHandler（子进程需要独立初始化）。


def _setup_env(env_vars):
    """在子进程中设置 RabbitMQ 环境变量"""
    for key, value in env_vars.items():
        os.environ[key] = value


def _new_handler():
    """在子进程中创建独立的 handler 实例"""
    RabbitMQMessageHandler._instance = None
    return RabbitMQMessageHandler()


def _worker_acquire(env_vars, thread_id, result_queue):
    """Worker：注册消费者并返回 consumer_id"""
    _setup_env(env_vars)
    h = _new_handler()
    cid = h.acquire_consumer(thread_id)
    result_queue.put({"pid": os.getpid(), "consumer_id": cid})


def _worker_check(env_vars, thread_id, consumer_id, result_queue):
    """Worker：检查 consumer_id 是否仍是活跃消费者"""
    _setup_env(env_vars)
    h = _new_handler()
    try:
        h.check_consumer(thread_id, consumer_id)
        result_queue.put({"pid": os.getpid(), "preempted": False})
    except ConsumerPreemptedError:
        result_queue.put({"pid": os.getpid(), "preempted": True})


def _worker_release(env_vars, thread_id, consumer_id, result_queue):
    """Worker：释放消费者（被抢占场景）"""
    _setup_env(env_vars)
    h = _new_handler()
    h.release_consumer(thread_id, consumer_id)
    result_queue.put({"pid": os.getpid(), "released": True})


def _worker_wait_exit(env_vars, thread_id, timeout, result_queue):
    """Worker：等待旧消费者退出"""
    _setup_env(env_vars)
    h = _new_handler()
    exited = h.wait_for_previous_consumer(thread_id, timeout=timeout)
    result_queue.put({"pid": os.getpid(), "exited": exited})


def _worker_put_and_flush(env_vars, thread_id, messages, result_queue):
    """Worker：写入消息并 flush"""
    _setup_env(env_vars)
    h = _new_handler()
    for msg in messages:
        h.put(thread_id, msg)
    h.flush(thread_id)
    result_queue.put({"pid": os.getpid(), "count": len(messages)})


def _worker_get_messages(env_vars, thread_id, timeout, result_queue):
    """Worker：消费消息"""
    _setup_env(env_vars)
    h = _new_handler()
    try:
        msgs = h.get(thread_id, timeout=timeout)
        result_queue.put({"pid": os.getpid(), "messages": msgs})
    except TimeoutError:
        result_queue.put({"pid": os.getpid(), "messages": []})


def _worker_get_dlq_count(env_vars, thread_id, result_queue):
    """Worker：获取 DLQ 消息数量"""
    _setup_env(env_vars)
    h = _new_handler()
    count = h._get_dlq_count(thread_id)
    result_queue.put({"pid": os.getpid(), "dlq_count": count})


def _worker_get_cached_count(env_vars, thread_id, result_queue):
    """Worker：获取主队列消息数量"""
    _setup_env(env_vars)
    h = _new_handler()
    count = h.get_cached_count(thread_id)
    result_queue.put({"pid": os.getpid(), "cached_count": count})


def _worker_clear(env_vars, thread_id, result_queue):
    """Worker：清空队列"""
    _setup_env(env_vars)
    h = _new_handler()
    h.clear(thread_id)
    result_queue.put({"pid": os.getpid(), "cleared": True})


def _worker_mark_completed(env_vars, thread_id, result_queue):
    """Worker：标记完成"""
    _setup_env(env_vars)
    h = _new_handler()
    h.mark_completed(thread_id)
    result_queue.put({"pid": os.getpid(), "completed": True})


def _worker_restore_messages(env_vars, thread_id, result_queue):
    """Worker：恢复 DLQ 消息到主队列"""
    _setup_env(env_vars)
    h = _new_handler()
    restored = h.restore_messages(thread_id)
    result_queue.put({"pid": os.getpid(), "restored": restored})


def _run_worker(ctx, target, args, timeout=15):
    """启动 spawn 子进程并获取结果"""
    result_queue = ctx.Queue()
    p = ctx.Process(target=target, args=(*args, result_queue))
    p.start()
    p.join(timeout=timeout)
    if p.exitcode != 0:
        raise RuntimeError(f"Worker process exited with code {p.exitcode}")
    return result_queue.get(timeout=5)


class TestMultiProcessAcquireAndCheck:
    """多进程：acquire + check 跨进程状态共享"""

    def test_cross_process_acquire_produces_unique_ids(self, mp_ctx, env_vars, handler, thread_id):
        """不同进程 acquire 返回不同 consumer_id"""
        r1 = _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))
        r2 = _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))

        assert r1["pid"] != r2["pid"], "应在不同进程中运行"
        assert r1["consumer_id"] != r2["consumer_id"], "两次 acquire 应产生不同 ID"

    def test_cross_process_preemption_detection(self, mp_ctx, env_vars, handler, thread_id):
        """进程 A acquire → 进程 B acquire → A 被抢占, B 活跃"""
        ra = _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))
        rb = _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))

        check_a = _run_worker(mp_ctx, _worker_check, (env_vars, thread_id, ra["consumer_id"]))
        assert check_a["preempted"] is True, "旧消费者 A 应被抢占"

        check_b = _run_worker(mp_ctx, _worker_check, (env_vars, thread_id, rb["consumer_id"]))
        assert check_b["preempted"] is False, "新消费者 B 应仍然活跃"

    def test_cross_process_multiple_acquire_only_latest_active(self, mp_ctx, env_vars, handler, thread_id):
        """4 次跨进程 acquire，只有最后一个有效"""
        consumer_ids = []
        for _ in range(4):
            r = _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))
            consumer_ids.append(r["consumer_id"])

        last_check = _run_worker(mp_ctx, _worker_check, (env_vars, thread_id, consumer_ids[-1]))
        assert last_check["preempted"] is False, "最新消费者应活跃"

        for i, old_cid in enumerate(consumer_ids[:-1]):
            old_check = _run_worker(mp_ctx, _worker_check, (env_vars, thread_id, old_cid))
            assert old_check["preempted"] is True, f"第 {i + 1} 个消费者应被抢占"


class TestMultiProcessReleaseAndWait:
    """多进程：release + wait 退出信号跨进程传递"""

    def test_exit_signal_delivered_cross_process(self, mp_ctx, env_vars, handler, thread_id):
        """被抢占消费者 release 后，新消费者 wait 能收到退出信号"""
        ra = _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))
        _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))

        release_r = _run_worker(mp_ctx, _worker_release, (env_vars, thread_id, ra["consumer_id"]))
        assert release_r["released"] is True

        wait_r = _run_worker(mp_ctx, _worker_wait_exit, (env_vars, thread_id, 3.0))
        assert wait_r["exited"] is True, "应收到旧消费者退出信号"

    def test_wait_timeout_when_no_signal(self, mp_ctx, env_vars, handler):
        """无退出信号时 wait 超时返回 False"""
        tid = f"test-mp-timeout-{int(time.time() * 1000) % 100000}"
        try:
            _run_worker(mp_ctx, _worker_acquire, (env_vars, tid))

            wait_r = _run_worker(mp_ctx, _worker_wait_exit, (env_vars, tid, 1.0))
            assert wait_r["exited"] is False, "无退出信号应超时"
        finally:
            handler = RabbitMQMessageHandler()
            handler.clear(tid)


class TestMultiProcessEndToEnd:
    """多进程：完整端到端流程"""

    def test_write_consume_preempt_restore_reconsume(self, mp_ctx, env_vars, handler, thread_id):
        """跨进程端到端：写入 → 消费 → 抢占 → DLQ恢复 → 重新消费

        模拟 gunicorn 多 worker 场景下的断点续传：
        1. 进程 I 写入 3 条消息
        2. 进程 J acquire
        3. 进程 K 消费消息（进入 DLQ）
        4. 进程 L acquire（抢占 J）
        5. 进程 M 验证 J 被抢占
        6. 进程 N release 旧消费者（恢复 DLQ + 发退出信号）
        7. 进程 O wait 收到退出信号
        8. 进程 P 验证 DLQ 已清空，主队列已恢复
        9. 进程 Q 重新消费
        """
        _run_worker(mp_ctx, _worker_clear, (env_vars, thread_id))

        msgs = ["e2e_1", "e2e_2", "e2e_3"]

        # 1. 写入消息
        ri = _run_worker(mp_ctx, _worker_put_and_flush, (env_vars, thread_id, msgs))
        assert ri["count"] == 3

        # 2. 消费者 J acquire
        rj = _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))
        consumer_j = rj["consumer_id"]

        # 3. 消费消息（进入 DLQ）
        rk = _run_worker(mp_ctx, _worker_get_messages, (env_vars, thread_id, 2))
        assert rk["messages"] == msgs

        # 验证 DLQ 有 3 条，主队列为 0
        r_dlq = _run_worker(mp_ctx, _worker_get_dlq_count, (env_vars, thread_id))
        assert r_dlq["dlq_count"] == 3
        r_cached = _run_worker(mp_ctx, _worker_get_cached_count, (env_vars, thread_id))
        assert r_cached["cached_count"] == 0

        # 4. 消费者 L acquire（抢占 J）
        rl = _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))
        consumer_l = rl["consumer_id"]
        assert consumer_l != consumer_j

        # 5. 验证 J 被抢占
        rm = _run_worker(mp_ctx, _worker_check, (env_vars, thread_id, consumer_j))
        assert rm["preempted"] is True

        # 6. release 旧消费者 J（恢复 DLQ + 退出信号）
        rn = _run_worker(mp_ctx, _worker_release, (env_vars, thread_id, consumer_j))
        assert rn["released"] is True

        # 7. wait 收到退出信号
        ro = _run_worker(mp_ctx, _worker_wait_exit, (env_vars, thread_id, 3.0))
        assert ro["exited"] is True

        # 8. 验证 DLQ 清空，主队列恢复
        r_dlq2 = _run_worker(mp_ctx, _worker_get_dlq_count, (env_vars, thread_id))
        assert r_dlq2["dlq_count"] == 0
        r_cached2 = _run_worker(mp_ctx, _worker_get_cached_count, (env_vars, thread_id))
        assert r_cached2["cached_count"] == 3

        # 9. 重新消费
        rq = _run_worker(mp_ctx, _worker_get_messages, (env_vars, thread_id, 2))
        assert rq["messages"] == msgs

        # 清理
        _run_worker(mp_ctx, _worker_mark_completed, (env_vars, thread_id))

    def test_cross_process_normal_flow(self, mp_ctx, env_vars, handler, thread_id):
        """跨进程正常流程（无抢占）：写入 → acquire → 消费 → mark_completed"""
        _run_worker(mp_ctx, _worker_clear, (env_vars, thread_id))

        msgs = ["nf_1", "nf_2", EOD_CHUNK]

        _run_worker(mp_ctx, _worker_put_and_flush, (env_vars, thread_id, msgs))

        ra = _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))
        consumer_id = ra["consumer_id"]

        check_r = _run_worker(mp_ctx, _worker_check, (env_vars, thread_id, consumer_id))
        assert check_r["preempted"] is False

        rg = _run_worker(mp_ctx, _worker_get_messages, (env_vars, thread_id, 2))
        assert rg["messages"] == msgs

        _run_worker(mp_ctx, _worker_mark_completed, (env_vars, thread_id))
        _run_worker(mp_ctx, _worker_release, (env_vars, thread_id, consumer_id))

    def test_cross_process_restore_without_preemption(self, mp_ctx, env_vars, handler, thread_id):
        """跨进程断点续传（无抢占）：写入 → 消费 → 断开 → restore → 重新消费"""
        _run_worker(mp_ctx, _worker_clear, (env_vars, thread_id))

        msgs = ["rs_1", "rs_2", "rs_3"]
        _run_worker(mp_ctx, _worker_put_and_flush, (env_vars, thread_id, msgs))

        _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))

        rg = _run_worker(mp_ctx, _worker_get_messages, (env_vars, thread_id, 2))
        assert rg["messages"] == msgs

        # 验证消息进入 DLQ
        r_dlq = _run_worker(mp_ctx, _worker_get_dlq_count, (env_vars, thread_id))
        assert r_dlq["dlq_count"] == 3

        # 模拟断开：直接 restore
        r_restore = _run_worker(mp_ctx, _worker_restore_messages, (env_vars, thread_id))
        assert r_restore["restored"] == 3

        # 验证主队列恢复
        r_cached = _run_worker(mp_ctx, _worker_get_cached_count, (env_vars, thread_id))
        assert r_cached["cached_count"] == 3

        # 重新消费
        rg2 = _run_worker(mp_ctx, _worker_get_messages, (env_vars, thread_id, 2))
        assert rg2["messages"] == msgs

        _run_worker(mp_ctx, _worker_mark_completed, (env_vars, thread_id))

    def test_cross_process_double_preemption(self, mp_ctx, env_vars, handler, thread_id):
        """跨进程双重抢占：A → B 抢占 → C 抢占 B，验证只有 C 活跃"""
        ra = _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))
        rb = _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))
        rc = _run_worker(mp_ctx, _worker_acquire, (env_vars, thread_id))

        check_a = _run_worker(mp_ctx, _worker_check, (env_vars, thread_id, ra["consumer_id"]))
        assert check_a["preempted"] is True

        check_b = _run_worker(mp_ctx, _worker_check, (env_vars, thread_id, rb["consumer_id"]))
        assert check_b["preempted"] is True

        check_c = _run_worker(mp_ctx, _worker_check, (env_vars, thread_id, rc["consumer_id"]))
        assert check_c["preempted"] is False

        # release A（被抢占）
        _run_worker(mp_ctx, _worker_release, (env_vars, thread_id, ra["consumer_id"]))
        # release B（被抢占）
        _run_worker(mp_ctx, _worker_release, (env_vars, thread_id, rb["consumer_id"]))
        # release C（正常）
        _run_worker(mp_ctx, _worker_release, (env_vars, thread_id, rc["consumer_id"]))
