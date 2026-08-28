from __future__ import annotations

import base64
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .trace import API_TRACE


def envelope(data=None, *, result: bool = True, message: str = "ok", code: str = "success") -> dict:
    return {"result": result, "data": data, "code": code, "message": message}


@dataclass
class MockState:
    username: str = "e2e-token-user"
    sessions: dict[str, dict] = field(default_factory=dict)
    contents: dict[int, dict] = field(default_factory=dict)
    requests: list[dict] = field(default_factory=list)
    next_content_id: int = 1
    lock: threading.Lock = field(default_factory=threading.Lock)


class RemoteMock:
    def __init__(self, host: str, port: int, token_username: str):
        self.state = MockState(username=token_username)
        handler = self._handler_type()
        self.server = ThreadingHTTPServer((host, port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, name="e2e-remote-mock", daemon=True)

    def _handler_type(self):
        state = self.state

        class Handler(BaseHTTPRequestHandler):
            server_version = "bk-aidev-agent-e2e-mock/1"

            def log_message(self, _format, *_args):
                return

            def _body(self):
                length = int(self.headers.get("Content-Length", "0") or 0)
                if not length:
                    return {}
                raw = self.rfile.read(length).decode("utf-8", errors="replace")
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"raw": raw}

            def _send(self, data, status=HTTPStatus.OK, content_type="application/json"):
                if isinstance(data, (dict, list)):
                    raw = json.dumps(data, ensure_ascii=False).encode()
                else:
                    raw = str(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", f"{content_type}; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                response_headers = {
                    "Content-Type": f"{content_type}; charset=utf-8",
                    "Content-Length": str(len(raw)),
                }
                API_TRACE.finish_call(
                    self._trace_call,
                    status=int(status),
                    response_headers=response_headers,
                    response_body=data,
                    duration_ms=round((time.monotonic() - self._trace_started) * 1000),
                )

            def _record(self, body):
                auth_mode = "username" if self.headers.get("X-BKAIDEV-USER") else "application"
                authorization = self.headers.get("Authorization") or self.headers.get("X-Bkapi-Authorization")
                if authorization:
                    auth_mode = "access_token"
                with state.lock:
                    state.requests.append(
                        {"method": self.command, "path": self.path, "auth_mode": auth_mode, "body": body}
                    )

            def _dispatch(self):
                self._trace_started = time.monotonic()
                parsed = urlparse(self.path)
                path = parsed.path
                openapi_marker = "/openapi/aidev/"
                if openapi_marker in path:
                    path = path[path.index(openapi_marker) :]
                body = self._body() if self.command in {"POST", "PUT", "PATCH"} else {}
                host = self.headers.get("Host", "local-remote-mock")
                self._trace_call = API_TRACE.start_call(
                    source="agent-to-remote-mock",
                    method=self.command,
                    url=f"http://{host}{self.path}",
                    request_headers=dict(self.headers.items()),
                    request_body=body,
                )
                self._record(body)

                if path == "/healthz":
                    return self._send({"status": "ok"})
                if path == "/api/v1/auth/access-tokens/verify" and self.command == "POST":
                    if not body.get("access_token"):
                        return self._send(
                            envelope(None, result=False, message="missing access token", code="invalid_token"), 401
                        )
                    return self._send(envelope({"username": state.username}))
                if path == "/api/v1/auth/login" and self.command == "POST":
                    username = body.get("username", "")
                    if not username:
                        return self._send(
                            envelope(None, result=False, message="missing username", code="invalid_user"), 400
                        )
                    return self._send(envelope({"username": username}))
                if path == "/openapi/aidev/resource/v1/agent_channel/configs/" and self.command == "GET":
                    return self._send(
                        envelope(
                            [
                                {
                                    "channel_id": "e2e-rtx",
                                    "channel_name": "E2E WeCom",
                                    "channel_type": "rtx",
                                    "connection_type": "websocket",
                                    "websocket_connected": True,
                                    "config": {
                                        "bot_id": "e2e-bot",
                                        "secret": "e2e-ws-secret",
                                        "ws_url": "ws://127.0.0.1",
                                        "contact": "E2E",
                                    },
                                }
                            ]
                        )
                    )
                if path == "/openapi/aidev/resource/v1/qyweixin/convert_to_userid/" and self.command == "POST":
                    return self._send(envelope({"userid": body.get("openid", "e2e-user")}))
                if path.startswith("/openapi/aidev/resource/v1/agent/") and self.command == "GET":
                    return self._send(envelope(agent_config()))
                if path == "/openapi/aidev/resource/v1/agents/llms/" and self.command == "GET":
                    return self._send(envelope([{"llm_code": "mock-model", "name": "Local deterministic model"}]))
                if path == "/v1/api/token_check" and self.command == "POST":
                    prompts = body.get("prompts", [])
                    return self._send({"prompts": [{"tokenCount": 8} for _ in prompts]})
                if path.startswith("/v1/chat/completions") and self.command == "POST":
                    return self._chat(body)
                if path.startswith("/openapi/aidev/resource/v1/chat/session_content"):
                    return self._session_content(path, parsed.query, body)
                if path.startswith("/openapi/aidev/resource/v1/chat/session"):
                    return self._session(path, parsed.query, body)
                return self._send(
                    envelope(None, result=False, message=f"unhandled mock route: {path}", code="not_found"), 404
                )

            def _session(self, path, query, body):
                root = "/openapi/aidev/resource/v1/chat/session/"
                if path == root and self.command == "POST":
                    code = str(uuid.uuid4())
                    item = {"session_code": code, "session_name": body.get("session_name", "E2E session"), **body}
                    item["session_code"] = code
                    state.sessions[code] = item
                    return self._send(envelope(item))
                if path == root and self.command == "GET":
                    values = list(state.sessions.values())
                    if "page" in parse_qs(query):
                        return self._send(envelope({"count": len(values), "results": values}))
                    return self._send(envelope(values))
                if path == root + "get_or_create/" and self.command == "POST":
                    code = body.get("session_code") or str(uuid.uuid4())
                    item = state.sessions.setdefault(
                        code, {"session_code": code, "session_name": "E2E session", **body}
                    )
                    return self._send(envelope(item))
                suffix = path.removeprefix(root).strip("/")
                if suffix.endswith("/ai_rename"):
                    code = suffix.split("/")[0]
                    state.sessions[code]["session_name"] = "Mock generated title"
                    return self._send(envelope(state.sessions[code]))
                if suffix.endswith("/context"):
                    code = suffix.split("/")[0]
                    values = []
                    for item in state.contents.values():
                        if item.get("session_code") != code:
                            continue
                        context_item = dict(item)
                        property_data = item.get("property") if isinstance(item.get("property"), dict) else {}
                        context_item["builtin_property"] = property_data.get("builtin_property") or {}
                        if property_data.get("extra") is not None:
                            context_item["extra"] = property_data["extra"]
                        values.append(context_item)
                    return self._send(envelope(values))
                if suffix:
                    code = suffix.split("/")[0]
                    item = state.sessions.get(code)
                    if not item:
                        return self._send(
                            envelope(None, result=False, message="session not found", code="not_found"), 404
                        )
                    if self.command == "GET":
                        return self._send(envelope(item))
                    if self.command == "PUT":
                        item.update(body)
                        return self._send(envelope(item))
                    if self.command == "DELETE":
                        state.sessions.pop(code, None)
                        return self._send(envelope(True))
                return self._send(
                    envelope(None, result=False, message="unsupported session operation", code="bad_request"), 400
                )

            def _session_content(self, path, query, body):
                root = "/openapi/aidev/resource/v1/chat/session_content/"
                if path == root and self.command == "POST":
                    identifier = state.next_content_id
                    state.next_content_id += 1
                    item = {"id": identifier, **body}
                    state.contents[identifier] = item
                    return self._send(envelope(item))
                if path == root + "content/" and self.command == "GET":
                    session_code = parse_qs(query).get("session_code", [""])[0]
                    values = [item for item in state.contents.values() if item.get("session_code") == session_code]
                    return self._send(envelope(values))
                suffix = path.removeprefix(root).strip("/")
                if suffix.isdigit():
                    identifier = int(suffix)
                    if self.command == "PUT":
                        state.contents.setdefault(identifier, {"id": identifier}).update(body)
                        return self._send(envelope(state.contents[identifier]))
                    if self.command == "DELETE":
                        state.contents.pop(identifier, None)
                        return self._send(envelope(True))
                if path.endswith(("/token_usage/", "/stop/", "/batch_delete/")):
                    return self._send(envelope(True))
                return self._send(
                    envelope(None, result=False, message="unsupported content operation", code="bad_request"), 400
                )

            def _chat(self, body):
                messages = body.get("messages") or []
                prompt_text = json.dumps(messages, ensure_ascii=False)
                has_tool_answer = any(
                    message.get("role") == "tool" for message in messages if isinstance(message, dict)
                )

                if "[E2E_ASK_USER]" in prompt_text and not has_tool_answer:
                    return self._ask_user_question(body)

                if "[E2E_ASK_USER]" in prompt_text and has_tool_answer:
                    content = "已收到你的选择：生产环境。"
                elif "[E2E_CONTEXT_TURN_2]" in prompt_text:
                    retained = "[E2E_CONTEXT_TURN_1]" in prompt_text
                    content = "多轮上下文完整：已看到第一轮和第二轮。" if retained else "多轮上下文缺失：未看到第一轮。"
                elif "[E2E_CONTEXT_TURN_1]" in prompt_text:
                    content = "第一轮上下文已记录。"
                elif "[E2E_SLOW_STREAM]" in prompt_text:
                    content = "这是用于验证断线恢复与停止生成的分段响应。"
                else:
                    content = "这是本地 mock LLM 的确定性回复。"
                if body.get("stream"):
                    parts = [content]
                    delay = 0.0
                    if "[E2E_SLOW_STREAM]" in prompt_text:
                        parts = ["这是用于", "验证断线恢复", "与停止生成", "的分段响应。"]
                        delay = 0.75
                    chunks = [
                        {
                            "id": "chatcmpl-e2e",
                            "object": "chat.completion.chunk",
                            "model": body.get("model", "mock-model"),
                            "choices": [{"delta": {"content": part}, "index": 0}],
                        }
                        for part in parts
                    ]
                    chunks.append(
                        {
                            "id": "chatcmpl-e2e",
                            "object": "chat.completion.chunk",
                            "model": body.get("model", "mock-model"),
                            "choices": [{"delta": {}, "finish_reason": "stop", "index": 0}],
                        }
                    )
                    return self._send_sse(chunks, delay=delay)
                return self._send(
                    {
                        "id": "chatcmpl-e2e",
                        "object": "chat.completion",
                        "model": body.get("model", "mock-model"),
                        "choices": [
                            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
                        ],
                        "usage": {"prompt_tokens": 8, "completion_tokens": 12, "total_tokens": 20},
                    }
                )

            def _ask_user_question(self, body):
                arguments = json.dumps(
                    {
                        "questions": [
                            {
                                "header": "部署确认",
                                "multiSelect": False,
                                "question": "请选择部署环境",
                                "options": [
                                    {"label": "测试环境", "description": "test"},
                                    {"label": "生产环境", "description": "prod"},
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
                chunks = [
                    {
                        "id": "chatcmpl-e2e-question",
                        "object": "chat.completion.chunk",
                        "model": body.get("model", "mock-model"),
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call_e2e_question",
                                            "type": "function",
                                            "function": {"name": "ask_user_question", "arguments": arguments},
                                        }
                                    ],
                                },
                            }
                        ],
                    },
                    {
                        "id": "chatcmpl-e2e-question",
                        "object": "chat.completion.chunk",
                        "model": body.get("model", "mock-model"),
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                    },
                ]
                return self._send_sse(chunks)

            def _send_sse(self, chunks, delay=0.0):
                frames = [f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n" for chunk in chunks]
                frames.append("data: [DONE]\n\n")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                sent: list[str] = []
                try:
                    for frame in frames:
                        self.wfile.write(frame.encode())
                        self.wfile.flush()
                        sent.append(frame)
                        if delay:
                            time.sleep(delay)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                API_TRACE.finish_call(
                    self._trace_call,
                    status=int(HTTPStatus.OK),
                    response_headers={"Content-Type": "text/event-stream; charset=utf-8"},
                    response_body="".join(sent),
                    duration_ms=round((time.monotonic() - self._trace_started) * 1000),
                )

            do_GET = _dispatch
            do_POST = _dispatch
            do_PUT = _dispatch
            do_DELETE = _dispatch

        return Handler

    def start(self):
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def agent_config() -> dict:
    otel_info = {
        "otel_url": "http://127.0.0.1:4318",
        "otel_token": "",
        "metrics": {"enabled": True, "export_interval_millis": 1000, "export_via_celery": False},
    }
    return {
        "agent_code": "e2e-agent",
        "agent_name": "E2E Agent",
        "agent_type": "common_qa",
        "agent_sdk_version": "e2e-local",
        "allowed_access": True,
        "space_id": "e2e-space",
        "prompt_setting": {
            "llm_code": "mock-model",
            "non_thinking_llm": "mock-model",
            "content": [{"role": "system", "content": "Answer only with deterministic local test data."}],
        },
        "knowledgebase_settings": {"knowledgebases": []},
        "intent_recognition": {},
        "conversation_settings": {"commands": [], "opening_remark": "Local E2E ready"},
        "related_tools": [],
        "related_skills": [],
        "mcp_server_config": {"mcpServers": {}},
        "resources": [],
        "related_agents": [],
        "otel_info": base64.b64encode(json.dumps(otel_info).encode()).decode(),
    }
