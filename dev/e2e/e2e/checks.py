from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import time
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

from .config import Config, Identity
from .http import request, with_query
from .report import CaseResult, RunReport
from .trace import API_TRACE


class Checks:
    def __init__(self, config: Config, identity: Identity, report: RunReport):
        self.config = config
        self.identity = identity
        self.report = report

    @contextmanager
    def case(self, module: str, name: str):
        started = time.monotonic()
        detail: dict = {}
        with API_TRACE.case(module, name):
            try:
                yield detail
            except Exception as error:
                self.report.cases.append(
                    CaseResult(module, name, "failed", round((time.monotonic() - started) * 1000), detail, str(error))
                )
            else:
                self.report.cases.append(
                    CaseResult(module, name, "passed", round((time.monotonic() - started) * 1000), detail)
                )

    @staticmethod
    def require(result, expected=(200,)):
        if result.status not in expected:
            raise AssertionError(f"HTTP {result.status}: {result.body}")
        return result

    def auth(self):
        with self.case("api", "登录 mock 与凭证优先级") as detail:
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
        with self.case("api", "远端 Session mock 生命周期") as detail:
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

        with self.case("api", "智能体 OpenAPI 真实应用链路") as detail:
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
        with self.case("ai-blueking", "页面与 Agent 配置") as detail:
            page = self.require(request("GET", self.config.app_url + "/chat-window/", headers=self.identity.headers))
            if "html" not in page.headers.get("Content-Type", "").lower():
                raise AssertionError("chat-window did not return HTML")
            info = self.require(
                request(
                    "GET", self.config.app_url + "/bk_plugin/openapi/agent/agent/info/", headers=self.identity.headers
                )
            )
            detail.update({"page_bytes": len(str(page.body).encode()), "agent": info.body})

        with self.case("ai-blueking", "浏览器渲染") as detail:
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

        with self.case("ai-blueking", "同步智能体对话到 mock LLM") as detail:
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
                    "case": "同步智能体对话到 mock LLM",
                    "conversation_id": result.body["data"].get("id", ""),
                    "messages": [
                        {"role": "user", "content": chat_request["input"]},
                        {"role": "assistant", "content": assistant_content},
                    ],
                }
            )

    def message(self):
        database_name = "真实 SQLite 应用数据库" if self.config.database == "sqlite" else "真实 MySQL 5.7 应用数据库"
        with self.case("message", database_name) as detail:
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

        with self.case("message", "真实 Redis PING") as detail:
            parsed = urllib.parse.urlparse(os.getenv("MESSAGE_REDIS_URL", "redis://127.0.0.1:16379/0"))
            with socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 6379), timeout=5) as stream:
                stream.sendall(b"*1\r\n$4\r\nPING\r\n")
                reply = stream.recv(64)
            if not reply.startswith(b"+PONG"):
                raise AssertionError(f"unexpected Redis response: {reply!r}")
            detail["response"] = reply.decode(errors="replace").strip()

        with self.case("message", "真实 RabbitMQ 发布与消费") as detail:
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
        with self.case("metrics", "真实 OTel exporter 上报") as detail:
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
        with self.case("metrics", "Prometheus 指标可查询") as detail:
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
        with self.case("metrics", "Grafana 仪表盘已预置") as detail:
            result = self.require(
                request("GET", "http://127.0.0.1:3000/api/dashboards/uid/aidev-agent-metrics", timeout=8)
            )
            detail.update({"title": result.body["dashboard"]["title"], "uid": result.body["dashboard"]["uid"]})

    def wxbot(self):
        with self.case("wxbot", "企微回调路由与真实 RabbitMQ 依赖") as detail:
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
