# -*- coding: utf-8 -*-
"""OpenTelemetry 测试目录的 conftest。

OTel 是 ``aidev_bkplugin`` 的可选 extras（``pip install aidev_bkplugin[opentelemetry]``），
未安装或版本组合不一致时整体跳过本目录，避免污染默认 ``make test`` 输出。
"""

import pytest

pytest.importorskip("opentelemetry", reason="install aidev_bkplugin[opentelemetry] to run OTel tests")

# OTel 各 wheel 必须版本一致；任何关键符号缺失即视为 extras 安装不完整，整体跳过。
try:
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter  # noqa: F401
    from opentelemetry.sdk._logs import LogRecord  # noqa: F401
except ImportError as exc:
    pytest.skip(
        f"opentelemetry extras 不完整或版本不一致: {exc}; 请重新执行 `uv pip install aidev_bkplugin[opentelemetry]`",
        allow_module_level=True,
    )
