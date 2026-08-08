# -*- coding: utf-8 -*-
"""``BKDjangoSaver`` 异步接口的真实 ORM 回归。

LangGraph 的 ainvoke / astream 会在事件循环里 await checkpointer 的 a* 方法，而 Django
游标带 async_unsafe 保护：任一 a* 方法只要在事件循环所在线程直接碰 ORM 就会抛
``SynchronousOnlyOperation``。这里用真实数据库跑通 aput → aput_writes → aget_tuple →
alist → adelete_thread 全链路，并显式断言同步实现被调度到了事件循环之外的线程，
避免未来重构（尤其是 alist 的惰性 QuerySet）把 ORM 漏回事件循环。

依赖 tests.settings 的文件型测试库：a* 方法在工作线程用的是独立连接，
必须与主线程看到同一个库。
"""

import threading
import uuid

import pytest
from aidev_bkplugin.models import Checkpoint, Write
from aidev_bkplugin.packages.checkpoint.bk_django_saver import BKDjangoSaver
from langgraph.checkpoint.base import empty_checkpoint

# transaction=True：a* 方法在别的线程/连接里读写，数据必须真实提交才可见
pytestmark = [pytest.mark.anyio, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def anyio_backend():
    """只跑 asyncio 后端，测试环境未装 trio。"""
    return "asyncio"


@pytest.fixture
def saver():
    return BKDjangoSaver(Checkpoint, Write)


@pytest.fixture
def thread_id():
    return uuid.uuid4().hex


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}


async def test_aput_then_aget_tuple_roundtrips_through_real_orm(saver, thread_id):
    config = _config(thread_id)
    checkpoint = empty_checkpoint()

    saved = await saver.aput(config, checkpoint, {"source": "input"}, {})

    assert saved["configurable"]["checkpoint_id"] == checkpoint["id"]
    assert await Checkpoint.objects.filter(thread_id=thread_id).acount() == 1

    loaded = await saver.aget_tuple(config)

    assert loaded is not None
    assert loaded.checkpoint["id"] == checkpoint["id"]
    assert loaded.metadata["source"] == "input"


async def test_aget_tuple_returns_none_for_unknown_thread(saver, thread_id):
    assert await saver.aget_tuple(_config(thread_id)) is None


async def test_aput_writes_are_visible_through_aget_tuple(saver, thread_id):
    saved = await saver.aput(_config(thread_id), empty_checkpoint(), {}, {})

    await saver.aput_writes(saved, [("messages", "hello")], "task-1")

    assert await Write.objects.filter(thread_id=thread_id).acount() == 1
    loaded = await saver.aget_tuple(saved)
    assert loaded.pending_writes == [("task-1", "messages", "hello")]


async def test_alist_evaluates_lazy_queryset_off_event_loop_thread(saver, thread_id):
    """alist 的核心回归：惰性 QuerySet 必须在工作线程内完成求值。

    实现若退回 ``for item in self.list(...)``，生成器会在事件循环线程被迭代，
    此时 consumed_in 记录到的就是事件循环线程（真实场景下更会直接抛
    SynchronousOnlyOperation）。
    """
    config = _config(thread_id)
    await saver.aput(config, empty_checkpoint(), {}, {})
    await saver.aput(config, empty_checkpoint(), {}, {})

    loop_thread = threading.current_thread()
    consumed_in: list[threading.Thread] = []
    original_list = saver.list

    def spy_list(*args, **kwargs):
        for item in original_list(*args, **kwargs):
            consumed_in.append(threading.current_thread())
            yield item

    saver.list = spy_list

    items = [item async for item in saver.alist(config)]

    assert len(items) == 2
    assert consumed_in, "alist 没有真正消费惰性生成器"
    assert all(t is not loop_thread for t in consumed_in)


async def test_adelete_thread_removes_checkpoints_and_writes(saver, thread_id):
    saved = await saver.aput(_config(thread_id), empty_checkpoint(), {}, {})
    await saver.aput_writes(saved, [("messages", "hello")], "task-1")

    await saver.adelete_thread(thread_id)

    assert await Checkpoint.objects.filter(thread_id=thread_id).acount() == 0
    assert await Write.objects.filter(thread_id=thread_id).acount() == 0


async def test_sync_implementations_are_dispatched_off_event_loop_thread(saver, thread_id):
    """aput / aput_writes / aget_tuple / adelete_thread 都不得在事件循环线程执行 ORM。"""
    loop_thread = threading.current_thread()
    executed_in: dict[str, threading.Thread] = {}

    def spy(name: str) -> None:
        original = getattr(saver, name)

        def wrapper(*args, **kwargs):
            executed_in[name] = threading.current_thread()
            return original(*args, **kwargs)

        setattr(saver, name, wrapper)

    for method in ("put", "put_writes", "get_tuple", "delete_thread"):
        spy(method)

    saved = await saver.aput(_config(thread_id), empty_checkpoint(), {}, {})
    await saver.aput_writes(saved, [("messages", "hello")], "task-1")
    await saver.aget_tuple(saved)
    await saver.adelete_thread(thread_id)

    assert set(executed_in) == {"put", "put_writes", "get_tuple", "delete_thread"}
    assert all(t is not loop_thread for t in executed_in.values())
