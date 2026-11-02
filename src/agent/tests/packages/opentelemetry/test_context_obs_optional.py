# -*- coding: utf-8 -*-
"""上下文观测入口在缺失 OTel extra 时仍可安全使用。"""

import subprocess
import sys

import pytest

NO_OTEL_PROGRAM = """
import importlib.abc
import sys

blocked_module = sys.argv[1]

class BlockOTel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == blocked_module or fullname.startswith(blocked_module + "."):
            raise ModuleNotFoundError("optional OTel dependency absent", name=fullname)

sys.meta_path.insert(0, BlockOTel())
if blocked_module != "opentelemetry":
    from opentelemetry import trace
from aidev_agent.packages.opentelemetry import context_obs as obs
from aidev_agent.core.nodes.model import model_chain, token_compression
with obs.observe_assembly(object()) as assembly:
    assert assembly is None
with obs.observe_compression_call(module="knowledge") as call:
    call.set_output(3)
if blocked_module != "opentelemetry.sdk":
    assert obs.measure_context(object()) is None
else:
    assert obs.measure_context(object()).total == 0
error = RuntimeError("business failure")
try:
    with obs.observe_compression_call(module="knowledge"):
        raise error
except RuntimeError as caught:
    assert caught is error
else:
    raise AssertionError("business error swallowed")
assert model_chain.observe_assembly is obs.observe_assembly
assert token_compression.observe_compression_call is obs.observe_compression_call
"""


@pytest.mark.parametrize("blocked_module", ["opentelemetry", "opentelemetry.instrumentation", "opentelemetry.sdk"])
def test_optional_otel_absence_keeps_business_paths_available(blocked_module):
    result = subprocess.run(
        [sys.executable, "-c", NO_OTEL_PROGRAM, blocked_module], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
