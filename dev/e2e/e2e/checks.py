from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

from .config import Config, Identity
from .http import request, stream_request, with_query
from .report import CaseResult, RunReport
from .trace import API_TRACE


def parse_sse_events(body: str) -> list[dict]:
    events: list[dict] = []
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line.removeprefix("data: ").strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def assistant_text(events: list[dict]) -> str:
    return "".join(str(event.get("delta", "")) for event in events if event.get("type") == "TEXT_MESSAGE_CONTENT")


def run_finished(events: list[dict], *, outcome: str | None = None) -> dict | None:
    candidates = [event for event in events if event.get("type") == "RUN_FINISHED"]
    if outcome is not None:
        candidates = [event for event in candidates if (event.get("outcome") or {}).get("type") == outcome]
    return candidates[-1] if candidates else None


class Checks:
    def __init__(self, config: Config, identity: Identity, report: RunReport):
        self.config = config
        self.identity = identity
        self.report = report

    @contextmanager
    def case(self, module: str, scenario_id: str, name: str, coverage: str):
        started = time.monotonic()
        detail: dict = {}
        with API_TRACE.case(module, name, scenario_id):
            try:
                yield detail
            except Exception as error:
                self.report.cases.append(
                    CaseResult(
                        module,
                        name,
                        "failed",
                        round((time.monotonic() - started) * 1000),
                        detail,
                        str(error),
                        coverage,
                        scenario_id,
                    )
                )
            else:
                self.report.cases.append(
                    CaseResult(
                        module,
                        name,
                        "passed",
                        round((time.monotonic() - started) * 1000),
                        detail,
                        coverage=coverage,
                        scenario_id=scenario_id,
                    )
                )

    @staticmethod
    def require(result, expected=(200,)):
        if result.status not in expected:
            raise AssertionError(f"HTTP {result.status}: {result.body}")
        return result

    def auth(self):
        with self.case(
            "api", "api.auth", "登录与身份解析", "username 登录 mock、access token 优先级和用户身份解析"
        ) as detail:
            if self.identity.mode == "access_token":
                result = request(
                    "POST",
                    self.config.mock_url + "/api/v1/auth/access-tokens/verify",
                    json_body={"access_token": self.identity.access_token},
                )
                self.require(result)
                resolved = result.body["data"]["username"]
            else:
                result = request(
                    "POST", self.config.mock_url + "/api/v1/auth/login", json_body={"username": self.identity.username}
                )
                self.require(result)
                resolved = result.body["data"]["username"]
            if resolved != self.identity.username:
                raise AssertionError(f"resolved username mismatch: {resolved}")
            detail.update({"auth_mode": self.identity.mode, "username": resolved})

    def api(self):
        headers = self.identity.headers
        root = self.config.mock_url + "/openapi/aidev/resource/v1/chat/session/"
        session_code = ""
        with self.case(
            "api", "api.remote-session", "远端 Session 生命周期", "Session 创建、列表、改名、详情回查和删除"
        ) as detail:
            created = self.require(request("POST", root, headers=headers, json_body={"session_name": "E2E"}))
            session_code = created.body["data"]["session_code"]
            listed = self.require(request("GET", root, headers=headers))
            updated = self.require(
                request("PUT", root + session_code + "/", headers=headers, json_body={"session_name": "E2E renamed"})
            )
            fetched = self.require(request("GET", root + session_code + "/", headers=headers))
            self.require(request("DELETE", root + session_code + "/", headers=headers))
            if not listed.body["data"] or fetched.body["data"]["session_name"] != "E2E renamed":
                raise AssertionError("session mock did not persist CRUD state")
            detail.update({"session_code": session_code, "updated": updated.body["data"]})

        with self.case(
            "api", "api.openapi", "智能体 OpenAPI", "Django 应用探活以及应用态 Session 创建、查询和删除"
        ) as detail:
            health = request("GET", self.config.app_url + "/bk_plugin/meta/", headers=headers, timeout=5)
            self.require(health)
            created = self.require(
                request(
                    "POST",
                    self.config.app_url + "/bk_plugin/openapi/agent/session/",
                    headers=headers,
                    json_body={"session_name": "E2E application session"},
                    timeout=30,
                )
            )
            app_session = created.body["data"]["session_code"]
            fetched = self.require(
                request(
                    "GET", self.config.app_url + f"/bk_plugin/openapi/agent/session/{app_session}/", headers=headers
                )
            )
            self.require(
                request(
                    "DELETE", self.config.app_url + f"/bk_plugin/openapi/agent/session/{app_session}/", headers=headers
                )
            )
            detail.update({"session_code": app_session, "response": fetched.body})

    def ai_blueking(self):
        chat_url = self.config.app_url + "/bk_plugin/openapi/agent/chat_completion/"
        content_url = self.config.app_url + "/bk_plugin/openapi/agent/session_content/"

        def create_session(name: str) -> str:
            created = self.require(
                request(
                    "POST",
                    self.config.app_url + "/bk_plugin/openapi/agent/session/",
                    headers=self.identity.headers,
                    json_body={"session_name": name},
                    timeout=30,
                )
            )
            return created.body["data"]["session_code"]

        def execute_stream(payload: dict, timeout: float = 90):
            result = self.require(
                stream_request(
                    "POST",
                    chat_url,
                    headers=self.identity.headers,
                    json_body=payload,
                    timeout=timeout,
                )
            )
            if "text/event-stream" not in result.headers.get("content-type", "").lower():
                raise AssertionError(f"chat completion did not return SSE: {result.headers}")
            return result, parse_sse_events(result.body)

        def record_conversation(scenario_id: str, case: str, conversation_id: str, messages: list[dict]) -> None:
            self.report.conversations.append(
                {
                    "module": "ai-blueking",
                    "scenario_id": scenario_id,
                    "case": case,
                    "conversation_id": conversation_id,
                    "messages": messages,
                }
            )

        with self.case(
            "ai-blueking",
            "ai-blueking.configuration",
            "页面与 Agent 配置",
            "AI 小鲸页面、Agent 基本信息、配置和访问权限",
        ) as detail:
            page = self.require(request("GET", self.config.app_url + "/chat-window/", headers=self.identity.headers))
            if "html" not in page.headers.get("Content-Type", "").lower():
                raise AssertionError("chat-window did not return HTML")
            info = self.require(
                request(
                    "GET", self.config.app_url + "/bk_plugin/openapi/agent/agent/info/", headers=self.identity.headers
                )
            )
            detail.update({"page_bytes": len(str(page.body).encode()), "agent": info.body})

        with self.case(
            "ai-blueking",
            "ai-blueking.browser-render",
            "浏览器渲染",
            "AI 小鲸页面在 Chrome/Chromium headed 或 headless 模式正常渲染",
        ) as detail:
            configured = os.getenv("E2E_BROWSER_BIN", "").strip()
            candidates = (
                configured,
                shutil.which("chromium") or "",
                shutil.which("chromium-browser") or "",
                shutil.which("google-chrome") or "",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            )
            browser = next((Path(item) for item in candidates if item and Path(item).is_file()), None)
            if browser is None:
                raise RuntimeError("Chrome/Chromium not found; configure E2E_BROWSER_BIN")
            command = [str(browser), "--no-first-run", "--no-default-browser-check"]
            if self.config.headless:
                result = subprocess.run(
                    [
                        *command,
                        "--headless=new",
                        "--disable-gpu",
                        "--disable-background-networking",
                        "--disable-extensions",
                        "--virtual-time-budget=5000",
                        "--dump-dom",
                        self.config.app_url + "/chat-window/",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if result.returncode or "<html" not in result.stdout.lower():
                    raise AssertionError(f"headless browser failed: {result.stderr[-500:]}")
                detail.update({"mode": "headless", "browser": browser.name, "dom_bytes": len(result.stdout.encode())})
            else:
                profile = self.config.root / "dev/e2e/.runtime/browser-profile"
                process = subprocess.Popen(
                    [*command, f"--user-data-dir={profile}", "--new-window", self.config.app_url + "/chat-window/"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(3)
                if process.poll() not in {None, 0}:
                    raise AssertionError(f"headed browser exited with {process.returncode}")
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
                detail.update({"mode": "headed", "browser": browser.name})

        with self.case(
            "ai-blueking",
            "ai-blueking.sync-chat",
            "同步智能体对话",
            "chat_completion、会话初始化、Token 计算、LLM 调用和会话内容写入",
        ) as detail:
            chat_request = {"input": "本地 E2E 测试", "execute_kwargs": {"stream": False}}
            result = self.require(
                request(
                    "POST",
                    self.config.app_url + "/bk_plugin/openapi/agent/chat_completion/",
                    headers=self.identity.headers,
                    json_body=chat_request,
                    timeout=90,
                )
            )
            assistant_content = result.body["data"]["choices"][0]["delta"]["content"]
            detail.update({"request": chat_request, "response": result.body})
            self.report.conversations.append(
                {
                    "module": "ai-blueking",
                    "scenario_id": "ai-blueking.sync-chat",
                    "case": "同步智能体对话",
                    "conversation_id": result.body["data"].get("id", ""),
                    "messages": [
                        {"role": "user", "content": chat_request["input"]},
                        {"role": "assistant", "content": assistant_content},
                    ],
                }
            )

        with self.case(
            "ai-blueking",
            "ai-blueking.stream-terminal",
            "流式消息与正常终态",
            "SSE 依次包含运行开始、文本增量、文本结束和当前运行的 RUN_FINISHED(success)",
        ) as detail:
            payload = {"input": "请用流式消息回复本地测试", "execute_kwargs": {"stream": True}}
            result, events = execute_stream(payload)
            event_types = [event.get("type") for event in events]
            required = {"RUN_STARTED", "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_END", "RUN_FINISHED"}
            if not required.issubset(set(event_types)) or run_finished(events, outcome="success") is None:
                raise AssertionError(f"incomplete successful stream: {event_types}")
            content = assistant_text(events)
            if not content:
                raise AssertionError("stream did not contain assistant text")
            session_code = result.headers.get("x-bkaidev-agent-session-code", "")
            detail.update(
                {
                    "session_code": session_code,
                    "message_handler": os.getenv("MESSAGE_HANDLER_TYPE", "redis"),
                    "event_types": event_types,
                    "terminal": run_finished(events, outcome="success"),
                }
            )
            record_conversation(
                "ai-blueking.stream-terminal",
                "流式消息与正常终态",
                session_code,
                [{"role": "user", "content": payload["input"]}, {"role": "assistant", "content": content}],
            )

        with self.case(
            "ai-blueking",
            "ai-blueking.multi-turn-context",
            "多轮上下文连续性",
            "同一 session 连续两轮对话，第二次 LLM 请求可见第一轮用户消息与助手回复",
        ) as detail:
            session_code = create_session("E2E multi-turn conversation")
            first_input = "[E2E_CONTEXT_TURN_1] 第一轮：项目代号是蓝鲸。"
            _, first_events = execute_stream(
                {"session_code": session_code, "input": first_input, "execute_kwargs": {"stream": True}}
            )
            if run_finished(first_events, outcome="success") is None:
                raise AssertionError("first turn did not create a completed session")
            second_input = "[E2E_CONTEXT_TURN_2] 第二轮：请确认仍记得第一轮。"
            _, second_events = execute_stream(
                {"session_code": session_code, "input": second_input, "execute_kwargs": {"stream": True}}
            )
            second_answer = assistant_text(second_events)
            if "多轮上下文完整" not in second_answer or run_finished(second_events, outcome="success") is None:
                raise AssertionError(f"second turn lost prior context: {second_answer}")
            detail.update(
                {
                    "session_code": session_code,
                    "turns": 2,
                    "first_terminal": run_finished(first_events, outcome="success"),
                    "second_terminal": run_finished(second_events, outcome="success"),
                }
            )
            record_conversation(
                "ai-blueking.multi-turn-context",
                "多轮上下文连续性",
                session_code,
                [
                    {"role": "user", "content": first_input},
                    {"role": "assistant", "content": assistant_text(first_events)},
                    {"role": "user", "content": second_input},
                    {"role": "assistant", "content": second_answer},
                ],
            )

        with self.case(
            "ai-blueking",
            "ai-blueking.disconnect-replay",
            "断线重连与消息回放",
            "客户端收到首段文本后主动断开，生产者继续运行；attach 重连可回放完整消息并收到成功终态",
        ) as detail:
            session_code = create_session("E2E reconnect conversation")
            payload = {
                "session_code": session_code,
                "input": "[E2E_SLOW_STREAM] 验证断线后重连",
                "execute_kwargs": {"stream": True},
            }
            disconnected = self.require(
                stream_request(
                    "POST",
                    chat_url,
                    headers=self.identity.headers,
                    json_body=payload,
                    timeout=90,
                    stop_after=lambda line: '"type":"TEXT_MESSAGE_CONTENT"' in line,
                )
            )
            partial_events = parse_sse_events(disconnected.body)
            if not assistant_text(partial_events) or run_finished(partial_events) is not None:
                raise AssertionError("disconnect point was not inside an active stream")
            reconnected, replay_events = execute_stream(
                {
                    "session_code": session_code,
                    "input": "",
                    "execute_kwargs": {"stream": True, "stream_mode": "attach"},
                },
                timeout=90,
            )
            replay_text = assistant_text(replay_events)
            if "断线恢复" not in replay_text or "分段响应" not in replay_text:
                raise AssertionError(f"replay did not restore the complete answer: {replay_text}")
            if run_finished(replay_events, outcome="success") is None:
                raise AssertionError("reconnected stream did not reach current successful terminal")
            detail.update(
                {
                    "session_code": session_code,
                    "partial_event_types": [event.get("type") for event in partial_events],
                    "replayed_event_types": [event.get("type") for event in replay_events],
                    "terminal": run_finished(replay_events, outcome="success"),
                    "reconnect_status": reconnected.status,
                }
            )
            record_conversation(
                "ai-blueking.disconnect-replay",
                "断线重连与消息回放",
                session_code,
                [
                    {"role": "user", "content": payload["input"]},
                    {"role": "assistant", "content": replay_text},
                ],
            )

        with self.case(
            "ai-blueking",
            "ai-blueking.stop-idempotent",
            "生成中停止与重复停止",
            "文本流生成期间携带当前 run_id 停止，消费者收敛到取消终态；重复停止不产生重复中断内容",
        ) as detail:
            session_code = create_session("E2E stop conversation")
            first_delta_seen = threading.Event()
            run_id_seen = threading.Event()
            captured: dict[str, object] = {"run_id": ""}

            def on_line(line: str) -> None:
                if not line.startswith("data: "):
                    return
                try:
                    event = json.loads(line.removeprefix("data: "))
                except json.JSONDecodeError:
                    return
                if event.get("type") == "RUN_STARTED":
                    captured["run_id"] = event.get("runId", "")
                    run_id_seen.set()
                if event.get("type") == "TEXT_MESSAGE_CONTENT":
                    first_delta_seen.set()

            def consume_slow_stream() -> None:
                try:
                    captured["result"] = stream_request(
                        "POST",
                        chat_url,
                        headers=self.identity.headers,
                        json_body={
                            "session_code": session_code,
                            "input": "[E2E_SLOW_STREAM] 请生成一段可停止的回复",
                            "execute_kwargs": {"stream": True},
                        },
                        timeout=90,
                        on_line=on_line,
                    )
                except Exception as error:  # pragma: no cover - surfaced by assertion below
                    captured["error"] = str(error)

            consumer = threading.Thread(target=consume_slow_stream, name="e2e-stop-stream", daemon=True)
            consumer.start()
            if not run_id_seen.wait(20) or not first_delta_seen.wait(20):
                raise AssertionError("slow stream did not reach the stoppable stage")
            stop_payload = {"session_code": session_code, "run_id": captured["run_id"]}
            first_stop = self.require(
                request(
                    "POST",
                    content_url + "stop/",
                    headers=self.identity.headers,
                    json_body=stop_payload,
                    timeout=30,
                )
            )
            consumer.join(timeout=30)
            if consumer.is_alive() or captured.get("error"):
                raise AssertionError(f"stream did not stop cleanly: {captured.get('error', 'still running')}")
            second_stop = self.require(
                request(
                    "POST",
                    content_url + "stop/",
                    headers=self.identity.headers,
                    json_body=stop_payload,
                    timeout=30,
                )
            )
            stream_result = captured.get("result")
            if stream_result is None:
                raise AssertionError("stopped stream result is missing")
            stopped_events = parse_sse_events(stream_result.body)
            terminal = run_finished(stopped_events)
            session = self.require(
                request(
                    "GET",
                    self.config.app_url + f"/bk_plugin/openapi/agent/session/{session_code}/",
                    headers=self.identity.headers,
                )
            ).body["data"]
            if terminal is None or terminal.get("runId") != "cancelled" or session.get("status") != "cancelled":
                raise AssertionError(f"stream did not expose a cancellation terminal: {terminal}")
            contents = self.require(
                request(
                    "GET",
                    with_query(content_url + "content/", session_code=session_code),
                    headers=self.identity.headers,
                )
            ).body["data"]
            interrupted = [
                item
                for item in contents
                if item.get("role") == "assistant"
                and (item.get("status") in {"cancelled", "error"} or "取消" in str(item.get("content", "")))
            ]
            if len(interrupted) > 1:
                raise AssertionError(f"duplicate interruption content after repeated stop: {interrupted}")
            detail.update(
                {
                    "session_code": session_code,
                    "run_id": captured["run_id"],
                    "terminal": terminal,
                    "session_status": session.get("status"),
                    "first_stop": first_stop.body,
                    "second_stop": second_stop.body,
                    "interruption_records": interrupted,
                }
            )
            record_conversation(
                "ai-blueking.stop-idempotent",
                "生成中停止与重复停止",
                session_code,
                [
                    {"role": "user", "content": "[E2E_SLOW_STREAM] 请生成一段可停止的回复"},
                    {"role": "assistant", "content": assistant_text(stopped_events) or "（生成已停止）"},
                ],
            )

        with self.case(
            "ai-blueking",
            "ai-blueking.ask-user-resume",
            "提问卡片答题与续流",
            "模型触发 ask_user_question 中断，提交选项后同一会话恢复并产出助手回复与当前运行成功终态",
        ) as detail:
            session_code = create_session("E2E ask-user-question conversation")
            question_input = "[E2E_ASK_USER] 部署前请先询问我要使用哪个环境。"
            _, question_events = execute_stream(
                {"session_code": session_code, "input": question_input, "execute_kwargs": {"stream": True}}
            )
            interrupt_terminal = run_finished(question_events, outcome="interrupt")
            interrupts = (interrupt_terminal or {}).get("outcome", {}).get("interrupts", [])
            if not interrupts:
                raise AssertionError(f"ask_user_question did not produce an interrupt: {interrupt_terminal}")
            interrupt = interrupts[0]
            interrupt_id = interrupt.get("id") or interrupt.get("interruptId") or ""
            metadata = interrupt.get("metadata") or {}
            if interrupt.get("reason") != "aidev:user_question" or not metadata.get("questions") or not interrupt_id:
                raise AssertionError(f"invalid ask_user_question payload: {interrupt}")
            answers = [
                {
                    "question": "请选择部署环境",
                    "answer": [{"label": "生产环境", "description": "prod"}],
                }
            ]
            _, resumed_events = execute_stream(
                {
                    "session_code": session_code,
                    "input": "",
                    "resume": [{"interruptId": interrupt_id, "payload": {"answers": answers}}],
                    "execute_kwargs": {"stream": True},
                }
            )
            resumed_text = assistant_text(resumed_events)
            if "已收到你的选择：生产环境" not in resumed_text:
                raise AssertionError(f"resume did not continue to the assistant answer: {resumed_text}")
            success_terminals = [
                event
                for event in resumed_events
                if event.get("type") == "RUN_FINISHED" and (event.get("outcome") or {}).get("type") == "success"
            ]
            if not success_terminals:
                raise AssertionError("resumed run did not expose its own successful terminal")
            replay_terminal_index = next(
                (index for index, event in enumerate(resumed_events) if event.get("type") == "RUN_FINISHED"), -1
            )
            run_started_index = next(
                (index for index, event in enumerate(resumed_events) if event.get("type") == "RUN_STARTED"), -1
            )
            assistant_index = next(
                (index for index, event in enumerate(resumed_events) if event.get("type") == "TEXT_MESSAGE_CONTENT"),
                -1,
            )
            current_terminal_index = max(
                index
                for index, event in enumerate(resumed_events)
                if event.get("type") == "RUN_FINISHED" and (event.get("outcome") or {}).get("type") == "success"
            )
            if not replay_terminal_index < run_started_index < assistant_index < current_terminal_index:
                raise AssertionError("old question-card terminal prematurely ended the resumed run")
            detail.update(
                {
                    "session_code": session_code,
                    "interrupt": interrupt,
                    "submitted_answers": answers,
                    "resumed_event_types": [event.get("type") for event in resumed_events],
                    "replayed_card_terminal": resumed_events[replay_terminal_index],
                    "success_terminal": success_terminals[-1],
                }
            )
            record_conversation(
                "ai-blueking.ask-user-resume",
                "提问卡片答题与续流",
                session_code,
                [
                    {"role": "user", "content": question_input},
                    {"role": "assistant", "content": "请选择部署环境：测试环境 / 生产环境"},
                    {"role": "user", "content": "生产环境"},
                    {"role": "assistant", "content": resumed_text},
                ],
            )

    def message(self):
        database_name = "真实 SQLite 应用数据库" if self.config.database == "sqlite" else "真实 MySQL 5.7 应用数据库"
        database_coverage = (
            "SQLite 文件完整性和 Django migration 落库"
            if self.config.database == "sqlite"
            else "MySQL 5.7 版本和应用库连接"
        )
        with self.case("message", "message.database", database_name, database_coverage) as detail:
            if self.config.database == "sqlite":
                path = self.config.root / "dev/e2e/.runtime/agent.sqlite3"
                if not path.is_file():
                    raise AssertionError(f"SQLite database was not created: {path}")
                connection = sqlite3.connect(path)
                try:
                    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                    migrations = connection.execute("SELECT COUNT(*) FROM django_migrations").fetchone()[0]
                finally:
                    connection.close()
                if integrity != "ok" or migrations < 1:
                    raise AssertionError(f"unexpected SQLite baseline: integrity={integrity}, migrations={migrations}")
                detail.update(
                    {
                        "backend": "sqlite",
                        "version": sqlite3.sqlite_version,
                        "database": path.name,
                        "integrity": integrity,
                        "migrations": migrations,
                    }
                )
            else:
                python = self.config.root / "template/builtin/{{cookiecutter.project_name}}/.venv/bin/python"
                script = """
import json, os, pymysql
connection = pymysql.connect(
    host=os.environ['MYSQL_HOST'], port=int(os.environ['MYSQL_PORT']),
    user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'],
    database=os.environ['MYSQL_NAME'],
)
with connection.cursor() as cursor:
    cursor.execute('SELECT VERSION(), DATABASE()')
    version, database = cursor.fetchone()
connection.close()
print(json.dumps({'version': version, 'database': database}))
"""
                checked = subprocess.run(
                    [str(python), "-c", script],
                    env=os.environ.copy(),
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                if checked.returncode:
                    raise AssertionError(f"MySQL check failed: {checked.stderr[-500:]}")
                mysql = json.loads(checked.stdout.splitlines()[-1])
                if not mysql["version"].startswith("5.7.") or mysql["database"] != os.getenv("MYSQL_NAME"):
                    raise AssertionError(f"unexpected MySQL baseline: {mysql}")
                detail.update({"backend": "mysql", **mysql})

        with self.case("message", "message.redis", "Redis 可用性", "真实 Redis 连接和 PING/PONG 往返") as detail:
            parsed = urllib.parse.urlparse(os.getenv("MESSAGE_REDIS_URL", "redis://127.0.0.1:16379/0"))
            with socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 6379), timeout=5) as stream:
                stream.sendall(b"*1\r\n$4\r\nPING\r\n")
                reply = stream.recv(64)
            if not reply.startswith(b"+PONG"):
                raise AssertionError(f"unexpected Redis response: {reply!r}")
            detail["response"] = reply.decode(errors="replace").strip()

        with self.case(
            "message", "message.rabbitmq", "RabbitMQ 消息往返", "真实队列创建、消息发布、消费确认和队列清理"
        ) as detail:
            user = os.getenv("RABBITMQ_USER", "aidev")
            password = os.getenv("RABBITMQ_PASSWORD", "aidev-e2e")
            host = os.getenv("RABBITMQ_HOST", "127.0.0.1")
            port = int(os.getenv("RABBITMQ_MANAGEMENT_PORT", "15673"))
            auth = base64.b64encode(f"{user}:{password}".encode()).decode()
            headers = {"Authorization": f"Basic {auth}"}
            queue = f"aidev-agent-e2e-{int(time.time() * 1000)}"
            queue_url = f"http://{host}:{port}/api/queues/%2F/{queue}"
            self.require(
                request(
                    "PUT",
                    queue_url,
                    headers=headers,
                    json_body={"auto_delete": True, "durable": False, "arguments": {}},
                ),
                (201, 204),
            )
            try:
                published = self.require(
                    request(
                        "POST",
                        f"http://{host}:{port}/api/exchanges/%2F/amq.default/publish",
                        headers=headers,
                        json_body={
                            "properties": {},
                            "routing_key": queue,
                            "payload": "e2e-message",
                            "payload_encoding": "string",
                        },
                    )
                )
                consumed = self.require(
                    request(
                        "POST",
                        f"http://{host}:{port}/api/queues/%2F/{queue}/get",
                        headers=headers,
                        json_body={"count": 1, "ackmode": "ack_requeue_false", "encoding": "auto", "truncate": 50000},
                    )
                )
                if (
                    not published.body.get("routed")
                    or not consumed.body
                    or consumed.body[0].get("payload") != "e2e-message"
                ):
                    raise AssertionError("RabbitMQ round trip failed")
                detail.update({"queue": queue, "payload": consumed.body[0]["payload"]})
            finally:
                request("DELETE", queue_url, headers=headers)

    def metrics(self):
        with self.case(
            "metrics", "metrics.otel-export", "OTel 指标上报", "Agent 指标经真实 OTel exporter 发送到本地 Collector"
        ) as detail:
            python = self.config.root / "template/builtin/{{cookiecutter.project_name}}/.venv/bin/python"
            environment = os.environ.copy()
            environment["PYTHONPATH"] = ":".join(
                (
                    str(self.config.root / "src/agent"),
                    str(self.config.root / "src/plugins/aidev_bkplugin"),
                    str(self.config.root),
                )
            )
            emitted = subprocess.run(
                [
                    str(python),
                    str(self.config.root / "dev/otel/mock_agent_metrics.py"),
                    "--handler",
                    "redis",
                    "--concurrency",
                    "1",
                    "--iterations",
                    "15",
                    "--interval",
                    "0.1",
                ],
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if emitted.returncode:
                raise AssertionError(f"metric exporter failed: {emitted.stderr[-1000:]}")
            time.sleep(2)
            detail["exporter"] = emitted.stdout.splitlines()[-1] if emitted.stdout else "completed"
        with self.case(
            "metrics", "metrics.prometheus", "Prometheus 指标查询", "Prometheus 就绪且可查询智能体 active 指标序列"
        ) as detail:
            health = self.require(request("GET", "http://127.0.0.1:9090/-/ready", timeout=8))
            query = self.require(
                request(
                    "GET",
                    with_query("http://127.0.0.1:9090/api/v1/query", query='{__name__=~"aidev_agent_active.*"}'),
                    timeout=8,
                )
            )
            if query.body.get("status") != "success":
                raise AssertionError("Prometheus query failed")
            if not query.body["data"]["result"]:
                raise AssertionError("Prometheus has no aidev_agent_active series")
            detail.update({"ready": health.body, "series": len(query.body["data"]["result"])})
        with self.case(
            "metrics", "metrics.grafana", "Grafana 仪表盘", "预置的 AIDev Agent Metrics 仪表盘可读取"
        ) as detail:
            result = self.require(
                request("GET", "http://127.0.0.1:3000/api/dashboards/uid/aidev-agent-metrics", timeout=8)
            )
            detail.update({"title": result.body["dashboard"]["title"], "uid": result.body["dashboard"]["uid"]})

    def wxbot(self):
        with self.case(
            "wxbot", "wxbot.callback", "企微签名回调", "企微消息加密签名、回调路由解密和真实 RabbitMQ 依赖"
        ) as detail:
            python = self.config.root / "template/builtin/{{cookiecutter.project_name}}/.venv/bin/python"
            script = """
import json
from aidev_wxbot.wxaibot.decryption import WXBizJsonMsgCrypt
crypt = WXBizJsonMsgCrypt('e2e-wxbot-token', 'abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG', '')
ret, payload = crypt.EncryptMsg('e2e-echo', 'e2e-nonce', '1787900000')
assert ret == 0
print(json.dumps(json.loads(payload)))
"""
            generated = subprocess.run(
                [str(python), "-c", script],
                env={
                    **os.environ,
                    "PYTHONPATH": str(self.config.root / "src/plugins/aidev_wxbot"),
                },
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if generated.returncode:
                raise AssertionError(f"wxbot callback payload generation failed: {generated.stderr[-500:]}")
            payload = json.loads(generated.stdout.splitlines()[-1])
            result = self.require(
                request(
                    "GET",
                    with_query(
                        self.config.app_url + "/wxbot_callback",
                        msg_signature=payload["msgsignature"],
                        timestamp=payload["timestamp"],
                        nonce=payload["nonce"],
                        echostr=payload["encrypt"],
                    ),
                    timeout=10,
                )
            )
            if result.body != "e2e-echo":
                raise AssertionError(f"unexpected wxbot echo: {result.body!r}")
            detail.update({"status": result.status, "response": result.body})

    def run(self):
        self.auth()
        handlers: dict[str, Callable[[], None]] = {
            "api": self.api,
            "ai-blueking": self.ai_blueking,
            "message": self.message,
            "metrics": self.metrics,
            "wxbot": self.wxbot,
        }
        for module in self.config.modules:
            handlers[module]()
