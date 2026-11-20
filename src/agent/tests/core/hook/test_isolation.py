# -*- coding: utf-8 -*-
"""实例隔离测试：同进程两个实例注入不同集合并发运行时互不串扰。

# AC14 test_two_instances_run_their_own_handlers
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from langchain_core.messages import AIMessage

from aidev_agent.core.hook import HookPoint, HookSet

from .conftest import make_config, run_node


class _ThreadScopedRecorder(logging.Handler):
    """按线程记录 hook 日志，用于断言日志中不出现对方的处理器标识。"""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        with self._lock:
            self.records.append((threading.current_thread().name, record.getMessage()))

    def messages_of(self, thread_name: str) -> list[str]:
        return [message for name, message in self.records if name == thread_name]


@pytest.fixture
def log_recorder():
    from aidev_agent.core.hook.runner import logger as hook_logger

    recorder = _ThreadScopedRecorder()
    level = hook_logger.level
    hook_logger.addHandler(recorder)
    hook_logger.setLevel(logging.INFO)
    try:
        yield recorder
    finally:
        hook_logger.removeHandler(recorder)
        hook_logger.setLevel(level)


def test_two_instances_run_their_own_handlers(fake_llm, build_model_node_with_hooks, log_recorder) -> None:
    """AC14 两个实例并发运行，各自只执行自己的处理器，日志不出现对方标识。"""
    seen: dict[str, list[str]] = {"alpha": [], "beta": []}

    def handler_alpha(context):
        seen["alpha"].append(context.identity.agent_code)

    def handler_beta(context):
        seen["beta"].append(context.identity.agent_code)

    alpha_hooks = HookSet({HookPoint.MODEL_PRE: [handler_alpha]})
    beta_hooks = HookSet({HookPoint.MODEL_PRE: [handler_beta]})
    alpha_llm = fake_llm([AIMessage(content="alpha")])
    beta_llm = fake_llm([AIMessage(content="beta")])
    alpha_node = build_model_node_with_hooks(alpha_llm, hooks=alpha_hooks)
    beta_node = build_model_node_with_hooks(beta_llm, hooks=beta_hooks)
    alpha_config = make_config(session_code="alpha", agent_code="alpha")
    beta_config = make_config(session_code="beta", agent_code="beta")

    def run_alpha():
        threading.current_thread().name = "alpha-run"
        return run_node(alpha_node, alpha_config)

    def run_beta():
        threading.current_thread().name = "beta-run"
        return run_node(beta_node, beta_config)

    with ThreadPoolExecutor(max_workers=2) as pool:
        alpha_result, beta_result = list(pool.map(lambda fn: fn(), [run_alpha, run_beta]))

    assert alpha_result["messages"][0].content == "alpha"
    assert beta_result["messages"][0].content == "beta"
    assert len(seen["alpha"]) == 1
    assert len(seen["beta"]) == 1

    alpha_logs = " ".join(log_recorder.messages_of("alpha-run"))
    beta_logs = " ".join(log_recorder.messages_of("beta-run"))
    assert "handler_alpha" in alpha_logs
    assert "handler_beta" not in alpha_logs
    assert "handler_beta" in beta_logs
    assert "handler_alpha" not in beta_logs
