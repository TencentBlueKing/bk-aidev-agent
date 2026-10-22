"""An optional evidence update must not hold chat completion indefinitely."""

import copy
import json
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from time import monotonic
from types import SimpleNamespace

import pytest
from ag_ui.core import CustomEvent, EventType
from aidev_agent.api.bk_aidev import Client
from aidev_agent.core.ag_ui.event_builders import build_model_end_payload
from aidev_agent.core.ag_ui.types import SessionPersistenceEventNames
from aidev_agent.services.agent.memory import completed_history
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.utils.message_metadata import finalize_memory_source
from langchain_core.messages import AIMessage


class StalledMetadataHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        row = {**payload, "id": 1}
        self.server.state.rows.append(copy.deepcopy(row))
        self.respond(row)

    def do_PUT(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if "status" in payload:
            self.server.state.statuses.append(payload["status"])
        else:
            self.server.state.updates.append(payload)
            self.server.state.release.wait(3)
            # Never commit the stalled metadata update.
        self.respond({})

    def respond(self, data):
        encoded = json.dumps({"result": True, "data": data}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        with suppress(BrokenPipeError, ConnectionResetError):
            self.wfile.write(encoded)

    def log_message(self, *args):
        pass


@pytest.fixture
def stalled_writer():
    server = ThreadingHTTPServer(("127.0.0.1", 0), StalledMetadataHandler)
    state = SimpleNamespace(rows=[], updates=[], statuses=[], release=Event())
    server.state = state
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = Client(endpoint=f"http://127.0.0.1:{server.server_port}/")
    try:
        yield AGUISessionWriter("session", client, username="alice"), state
    finally:
        state.release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def seed_stalled_answer(writer):
    answer = AIMessage(
        id="answer",
        content="Completed answer",
        response_metadata={
            "memory_source_pending": True,
            "memory_source_complete": False,
            "source_timestamp": "2026-10-22T00:00:00Z",
        },
    )
    writer(
        CustomEvent(
            type=EventType.CUSTOM,
            name=SessionPersistenceEventNames.ChatModelEnd.value,
            value=build_model_end_payload(answer, {}),
        )
    )
    return answer


def test_stalled_finalization_returns_without_qualifying_evidence(monkeypatch, stalled_writer):
    writer, state = stalled_writer
    # The actual default is asserted separately at the Operation/Session boundary.
    monkeypatch.setattr(writer, "_MEMORY_SOURCE_UPDATE_TIMEOUT", 0.15)
    answer = seed_stalled_answer(writer)
    started = monotonic()
    writer(
        CustomEvent(
            type=EventType.CUSTOM,
            name=SessionPersistenceEventNames.MemorySourceFinalized.value,
            value=finalize_memory_source(answer),
        )
    )
    assert monotonic() - started < 1.5
    assert writer._write_error_count == 1 and len(state.updates) == 1
    assert state.rows[0]["content"] == "Completed answer" and state.rows[0]["status"] == "complete"
    history = [{**row, "builtin_property": row["property"]["builtin_property"]} for row in state.rows]
    assert completed_history(history, "session") == []
    assert writer._assistant_builtin_properties["answer"]["memory_source_complete"] is False
    writer.set_streaming_finished()
    assert state.statuses == ["finished"]
