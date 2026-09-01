"""审批轮询退避序列与终态判定。"""

import pytest
from aidev_wxbot.wxaibot.approval_poll import (
    approval_poll_intervals,
    is_final_approve_result,
    wait_for_approval_result,
)
from aidev_wxbot.wxaibot.constants import (
    APPROVAL_POLL_MAX_INTERVAL_SECONDS,
    APPROVAL_POLL_MAX_SECONDS,
    WECOM_REPLY_WINDOW_SECONDS,
)


def test_approval_poll_intervals_double_then_cap_across_wecom_window():
    waits = approval_poll_intervals()
    assert waits[:8] == [2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0]
    assert all(wait <= APPROVAL_POLL_MAX_INTERVAL_SECONDS for wait in waits)
    assert waits[8] == APPROVAL_POLL_MAX_INTERVAL_SECONDS
    assert waits[-1] == APPROVAL_POLL_MAX_SECONDS - sum(waits[:-1])
    assert sum(waits) == APPROVAL_POLL_MAX_SECONDS == WECOM_REPLY_WINDOW_SECONDS


def test_approval_poll_intervals_truncate_last_slice():
    assert approval_poll_intervals(initial=2, cap=8, max_seconds=10) == [2, 4, 4]


@pytest.mark.parametrize(
    "info, expected",
    [
        ({"approve_result": "approved"}, True),
        ({"approve_result": "rejected"}, True),
        ({"approve_result": "cancelled"}, True),
        ({"approve_result": "pending"}, False),
        ({}, False),
        (None, False),
    ],
)
def test_final_approve_result(info, expected):
    assert is_final_approve_result(info) is expected


async def test_wait_for_approval_result_returns_on_first_hit():
    calls = []

    async def query():
        calls.append(1)
        return {"approve_result": "approved"}

    slept = []
    info = await wait_for_approval_result(query, sleep=slept.append, intervals=[2, 4])
    assert info == {"approve_result": "approved"}
    assert calls == [1]
    assert slept == []


async def test_wait_for_approval_result_logs_each_backoff_interval(caplog):
    results = [None, {"approve_result": "pending"}, {"approve_result": "approved"}]

    async def query():
        return results.pop(0)

    with caplog.at_level("INFO"):
        info = await wait_for_approval_result(query, sleep=_noop_sleep, intervals=[2, 4], session_code="sc-1")
    assert info == {"approve_result": "approved"}
    assert "interval_seconds=2" in caplog.text
    assert "interval_seconds=4" in caplog.text
    assert "session_code=sc-1" in caplog.text


async def _noop_sleep(_wait):
    return None


async def test_wait_for_approval_result_uses_backoff_until_final():
    results = [None, {"approve_result": "pending"}, {"approve_result": "rejected"}]

    async def query():
        return results.pop(0)

    slept = []

    async def sleep(wait):
        slept.append(wait)

    info = await wait_for_approval_result(query, sleep=sleep, intervals=[2, 4, 8])
    assert info == {"approve_result": "rejected"}
    assert slept == [2, 4]


async def test_wait_for_approval_result_times_out():
    async def query():
        return None

    slept = []

    async def sleep(wait):
        slept.append(wait)

    assert await wait_for_approval_result(query, sleep=sleep, intervals=[1, 2]) is None
    assert slept == [1, 2]
