# -*- coding: utf-8 -*-
"""RUN_FINISHED.timestamp 与本轮最后一条 assistant 入库毫秒对齐。"""

import json
from unittest.mock import MagicMock

from ag_ui.core import EventType, RunFinishedEvent
from ag_ui.encoder import EventEncoder

from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.utils import event as event_utils


def test_run_finished_timestamp_equals_assistant_created_at_ms():
    """SSE 编码后的 RUN_FINISHED.timestamp 等于本轮最后一条 assistant 的入库毫秒。"""
    client = MagicMock()
    client.api.create_chat_session_content.return_value = {
        "data": {"id": 1, "created_at": "2026-10-14T03:04:40.237598Z"}
    }
    writer = AGUISessionWriter("sess", client)
    writer._write_assistant_message("m1", "hello", [])
    event = RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id="t1", run_id="run-1")

    # 与 AidevAGUIAgent._dispatch_event 顺序一致：墙钟打戳 → 回写 → SSE 编码
    event_utils.stamp_round_end_event(event)
    writer(event)
    payload = json.loads(EventEncoder().encode(event).removeprefix("data: ").strip())

    assert payload["timestamp"] == 1_791_947_080_237
