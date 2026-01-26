# -*- coding: utf-8 -*-
"""测试 ContextAssembly 中间件基础设施。"""

import pytest
from aidev_agent.core.nodes.model.context_assembly import MiddlewarePipeline
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext


class TestMiddlewarePipeline:
    def test_execute_runs_in_order(self):
        pipeline = MiddlewarePipeline()
        calls: list[str] = []

        def mw1(ctx: ProcessorContext, next_):
            calls.append("mw1:before")
            next_()
            calls.append("mw1:after")

        def mw2(ctx: ProcessorContext, next_):
            calls.append("mw2")
            next_()

        pipeline.use(mw1)
        pipeline.use(mw2)

        pipeline.execute(ProcessorContext(state={}, config={}))

        assert calls == ["mw1:before", "mw2", "mw1:after"]

    def test_execute_can_short_circuit(self):
        pipeline = MiddlewarePipeline()
        calls: list[str] = []

        def mw1(ctx: ProcessorContext, next_):
            calls.append("mw1")
            # 不调用 next_()，短路

        def mw2(ctx: ProcessorContext, next_):
            calls.append("mw2")
            next_()

        pipeline.use(mw1)
        pipeline.use(mw2)

        pipeline.execute(ProcessorContext(state={}, config={}))

        assert calls == ["mw1"]

    def test_execute_raises_if_next_called_twice(self):
        pipeline = MiddlewarePipeline()

        def bad_mw(ctx: ProcessorContext, next_):
            next_()
            next_()

        pipeline.use(bad_mw)

        with pytest.raises(RuntimeError, match=r"next\(\) called multiple times"):
            pipeline.execute(ProcessorContext(state={}, config={}))
