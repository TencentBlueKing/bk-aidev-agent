from __future__ import annotations

import pytest
from aidev_agent.utils import decorator as decorator_module


def test_external_retry_records_scheduled_and_exhausted(mocker):
    retry_metric = mocker.patch.object(decorator_module, "record_operation_retry")
    timeout_metric = mocker.patch.object(decorator_module, "record_operation_timeout")
    mocker.patch.object(decorator_module, "is_timeout_error", return_value=True)
    mocker.patch.object(decorator_module, "current_operation_scope", return_value="external")
    calls = 0

    @decorator_module.retry(max_retries=2, max_seconds=30)
    def _always_times_out():
        nonlocal calls
        calls += 1
        raise TimeoutError("sanitized external timeout")

    with pytest.raises(TimeoutError):
        _always_times_out()

    assert calls == 2
    assert [call.kwargs["outcome"] for call in retry_metric.call_args_list] == ["scheduled", "exhausted"]
    assert all(call.kwargs["error"].__class__ is TimeoutError for call in retry_metric.call_args_list)
    assert [call.kwargs["scope"] for call in timeout_metric.call_args_list] == ["external", "external"]
