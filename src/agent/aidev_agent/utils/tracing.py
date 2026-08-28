# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

宿主进程接入 Agent trace 的工具：读当前 trace id、开请求级 root span、装全局 provider。

面向的是「自己起进程驱动 Agent」的宿主（企微长连接是第一个，Celery worker、
常驻消费者同理）。走 HTTP 的宿主由 blueapps + ``BkAidevAgentInstrumentor`` 兜住，
用不上这里。

独立于 ``packages.opentelemetry``：那个包的 __init__ 会连带导入 exporter，未装
otel extras 的部署会直接 ImportError。本模块整体降级为空操作——宿主不该因为缺一个
观测依赖就起不来，落库这类核心链路更不能被拖垮。
"""

import contextlib
from collections.abc import Iterator
from logging import getLogger
from typing import Any, Optional

logger = getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.context import Context
except ImportError:  # pragma: no cover - 取决于部署时是否安装 otel
    trace = None
    Context = None

try:
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
except ImportError:  # pragma: no cover - SDK 与 instrumentation 同样是可选 extras
    RequestsInstrumentor = None
    TracerProvider = None
    ConsoleSpanExporter = None
    SimpleSpanProcessor = None

_tracer = trace.get_tracer(__name__) if trace is not None else None


def current_trace_id() -> str:
    """当前 span 的 32 位 hex trace id；无有效 span 时返回空串。

    不像 turn_id 那样逐层透传，是因为 OTel context 本来就跟着执行走：producer 线程
    显式 copy_context，跨进程有 ExecuteKwargs.caller_trace_context。再铺一条平行的
    参数链只会多出漏传的可能。
    """
    if trace is None:
        return ""
    span_context = trace.get_current_span().get_span_context()
    return format(span_context.trace_id, "032x") if span_context.is_valid else ""


@contextlib.contextmanager
def start_request_span(name: str, **attributes: Any) -> Iterator[str]:
    """为一次请求开一条独立 trace，yield 其 trace id（不可用时为空串）。

    ``agent.execution`` 会自动挂到它下面：``BkAidevAgentInjector.on_bk_agent_start``
    在没有上游 caller_trace_context 时传 ``context=None``，也就是取当前 context。

    显式传空 Context 强制成为 root span。常驻 worker 线程上可能残留上一次执行未
    detach 的 OTel context（LangChain 回调在生成器被中途丢弃时不保证走到
    on_chain_end），继承过去会让不同请求共用同一个 trace id。
    """
    if _tracer is None:
        yield ""
        return
    with _tracer.start_as_current_span(name, context=Context()) as span:
        for key, value in attributes.items():
            if value:
                span.set_attribute(key, value)
        yield current_trace_id()


def setup_tracing(*, console: bool = False) -> bool:
    """装上全局 TracerProvider 并让出站 requests 自动带 traceparent，返回是否装上。

    两件事都是必须的，缺一条 trace 就断在半路：

    1. ``BkAidevAgentInstrumentor`` 自建 provider 且刻意不注册为全局（见其 docstring
       「默认使用由 BkAidevAgentInstrumentor 提供的 tracer_provider 而不是全局的」），
       所以全局这里始终是 NoOp，本模块起的 span 拿不到有效 trace id。
    2. 平台侧接口有的走宿主自己的 client、有的走 aidev_bkplugin 的 bkapi client，
       手工注入总会漏；只能在 requests 这一层统一注入。

    日志里的 provider 标明 span 去了哪：``agent_sdk`` 复用了 Agent 的 exporter，能在
    APM 上看到；``standalone`` 是 Agent 侧 OTel 未启用时的兜底，trace id 有效且会透传
    给平台，但本地不上报——平台侧仍能把一轮对话聚成一条 trace，只是缺了宿主这一段。

    Args:
        console: 把 span 摘要打到终端，见 :func:`_attach_console_exporter`。
    """
    if trace is None or TracerProvider is None or RequestsInstrumentor is None:
        logger.info("event=agent_tracing_setup enabled=false reason=extras_missing")
        return False

    agent_provider = _agent_tracer_provider()
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        # 已经有人设过全局（重复调用或宿主自行初始化），再设会被 OTel 拒绝并告警
        source = "existing"
    elif agent_provider is not None:
        trace.set_tracer_provider(agent_provider)
        source = "agent_sdk"
    else:
        trace.set_tracer_provider(TracerProvider())
        source = "standalone"

    RequestsInstrumentor().instrument()
    attached = _attach_console_exporter() if console else False
    logger.info("event=agent_tracing_setup enabled=true provider=%s console=%s", source, attached)
    return True


def _agent_tracer_provider() -> Optional[Any]:
    """取 ``BkAidevAgentInstrumentor`` 已启动的 provider；取不到时为 None。

    延迟导入：``packages.opentelemetry`` 的 __init__ 会连带导入 exporter，模块级
    导入会让未装 extras 的部署连 current_trace_id 都用不上。
    """
    try:
        from aidev_agent.packages.opentelemetry.instrumentor import get_agent_tracer_provider
    except ImportError:  # pragma: no cover - 未装 otel extras
        return None
    return get_agent_tracer_provider()


def _format_span_line(span) -> str:
    """一行一个 span：靠 span/parent 两列就能把树拼出来，不必读整段 JSON。"""
    span_context = span.get_span_context()
    duration_ms = (span.end_time - span.start_time) / 1_000_000 if span.end_time else 0
    parent = format(span.parent.span_id, "016x") if span.parent else "root"
    return (
        f"[span] trace={format(span_context.trace_id, '032x')} "
        f"span={format(span_context.span_id, '016x')} parent={parent} "
        f"{duration_ms:>8.0f}ms {span.name}\n"
    )


def _attach_console_exporter() -> bool:
    """把 span 摘要打到终端，返回是否挂上。

    本地排查用：APM 上看不到 span 时，先在这里确认它到底有没有产出，免得在
    「没埋点」和「没上报」之间来回猜。挂到当前生效的 provider 上而不是新建一个，
    否则打印出来的是另一棵树。用 Simple 而非 Batch，退出前不刷新就白打了。
    """
    provider = trace.get_tracer_provider()
    if not hasattr(provider, "add_span_processor"):
        return False
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(formatter=_format_span_line)))
    return True
