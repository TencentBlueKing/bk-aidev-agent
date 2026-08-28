from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

SENSITIVE_KEY = re.compile(
    r"(^|[-_])(access[-_]?token|refresh[-_]?token|id[-_]?token|otel[-_]?token|token|secret|password|cookie|"
    r"authorization|signature|msg[-_]?signature|api[-_]?key)($|[-_])",
    re.I,
)
SENSITIVE_QUERY = re.compile(
    r"([?&](?:access_token|token|secret|password|cookie|authorization|signature|msg_signature|api[-_]?key)=)[^&]*",
    re.I,
)


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {
            key: "***MASKED***" if SENSITIVE_KEY.search(str(key)) else redact(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item, secrets) for item in value)
    if isinstance(value, str):
        result = value
        for secret in secrets:
            if secret:
                result = result.replace(secret, "***MASKED***")
        return SENSITIVE_QUERY.sub(r"\1***MASKED***", result)
    return value


@dataclass
class CaseResult:
    module: str
    name: str
    status: str
    duration_ms: int
    detail: Any = None
    error: str = ""


@dataclass
class RunReport:
    started_at: str
    modules: list[str]
    auth_mode: str = "unresolved"
    cases: list[CaseResult] = field(default_factory=list)
    conversations: list[dict[str, Any]] = field(default_factory=list)
    api_calls: list[dict[str, Any]] = field(default_factory=list)
    finished_at: str = ""

    def finish(self) -> None:
        self.finished_at = datetime.now().astimezone().isoformat(timespec="seconds")

    @property
    def passed(self) -> int:
        return sum(case.status == "passed" for case in self.cases)

    @property
    def failed(self) -> int:
        return sum(case.status == "failed" for case in self.cases)


def _pretty(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return html.escape(text)


def _complete_json(value: Any) -> str:
    return html.escape(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _render_conversations(conversations: list[dict[str, Any]]) -> str:
    rows = []
    role_names = {"user": "用户", "assistant": "助手", "system": "系统"}
    for conversation in conversations:
        messages = []
        for message in conversation.get("messages", []):
            role = str(message.get("role", "unknown"))
            content = message.get("content", "")
            rendered = html.escape(content) if isinstance(content, str) else _complete_json(content)
            messages.append(
                f'<div class="message {html.escape(role)}"><b>{html.escape(role_names.get(role, role))}</b>'
                f"<div>{rendered}</div></div>"
            )
        conversation_id = conversation.get("conversation_id") or "未返回"
        rows.append(
            '<article class="card conversation">'
            f"<h3>{html.escape(str(conversation.get('case', '会话')))}</h3>"
            f'<p class="meta">会话标识：<code>{html.escape(str(conversation_id))}</code></p>'
            f"{''.join(messages)}</article>"
        )
    return "".join(rows) or '<section class="card empty">本次执行未产生会话内容。</section>'


def _render_api_calls(api_calls: list[dict[str, Any]]) -> str:
    rows = []
    source_names = {
        "test-runner": "测试端请求",
        "agent-to-remote-mock": "智能体 → 远端 mock",
    }
    for call in api_calls:
        status = call.get("status")
        error = call.get("error", "")
        passed = isinstance(status, int) and status < 400 and not error
        css_class = "passed" if passed else "failed"
        status_text = str(status) if status is not None else "ERROR"
        source = source_names.get(str(call.get("source", "")), str(call.get("source", "unknown")))
        request_body = _complete_json(call.get("request_body"))
        request_headers = _complete_json(call.get("request_headers", {}))
        response_body = _complete_json(call.get("response_body"))
        response_headers = _complete_json(call.get("response_headers", {}))
        error_html = f'<p class="error">{html.escape(str(error))}</p>' if error else ""
        rows.append(
            f'<details class="api-call {css_class}"><summary>'
            f'<span class="sequence">#{call.get("sequence")}</span> '
            f'<span class="source">{html.escape(source)}</span> '
            f'<code class="method">{html.escape(str(call.get("method", "")))}</code> '
            f'<code class="url">{html.escape(str(call.get("url", "")))}</code> '
            f'<span class="status">{html.escape(status_text)}</span>'
            f"<small>{call.get('duration_ms', 0)} ms</small></summary>"
            f'<p class="meta">所属用例：{html.escape(str(call.get("module", "")))} · '
            f"{html.escape(str(call.get('case', '')))}</p>{error_html}"
            '<div class="exchange"><section><h4>请求 Headers</h4>'
            f"<pre>{request_headers}</pre><h4>请求 Body</h4><pre>{request_body}</pre></section>"
            "<section><h4>响应 Headers</h4>"
            f"<pre>{response_headers}</pre><h4>响应 Body</h4><pre>{response_body}</pre></section></div></details>"
        )
    return "".join(rows) or '<section class="card empty">本次执行未记录到 HTTP 调用。</section>'


def write_report(report: RunReport, report_dir: Path, secrets: tuple[str, ...] = ()) -> Path:
    report.finish()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output_dir = report_dir / stamp
    output_dir.mkdir(parents=True, exist_ok=False)
    safe = redact(asdict(report), secrets)
    json_path = output_dir / "result.json"
    json_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = []
    for case in safe["cases"]:
        icon = "✓" if case["status"] == "passed" else "✗"
        detail = _pretty(case.get("detail"))
        error = html.escape(case.get("error", ""))
        rows.append(
            f'<details class="{case["status"]}"><summary><span>{icon}</span> '
            f"{html.escape(case['module'])} · {html.escape(case['name'])} "
            f"<small>{case['duration_ms']} ms</small></summary>"
            f"{f'<p class=error>{error}</p>' if error else ''}"
            f"{f'<pre>{detail}</pre>' if detail else ''}</details>"
        )
    conversations = _render_conversations(safe["conversations"])
    api_calls = _render_api_calls(safe["api_calls"])
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>bk-aidev-agent E2E report</title><style>
body{{font:14px/1.5 system-ui;margin:0;background:#f5f7fa;color:#17233d}}main{{max-width:1100px;margin:32px auto;padding:0 20px}}
.card,details{{background:white;border:1px solid #e5e7eb;border-radius:8px;margin:10px 0;padding:14px}}summary{{cursor:pointer;font-weight:600}}
.passed summary span{{color:#169c51}}.failed summary span,.error{{color:#d4380d}}small{{float:right;color:#7a869a;font-weight:400}}
pre{{overflow:auto;background:#0b1020;color:#d9e2f2;padding:14px;border-radius:6px;white-space:pre-wrap;overflow-wrap:anywhere}}
code{{font-family:ui-monospace}}h2{{margin:28px 0 10px}}h3,h4{{margin:0 0 8px}}.meta,.empty{{color:#667085}}
.conversation .message{{max-width:82%;margin:12px 0;padding:12px 14px;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere}}
.conversation .user{{margin-left:auto;background:#e8f3ff}}.conversation .assistant{{background:#f2f4f7}}
.exchange{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.exchange section{{min-width:0}}
.api-call summary{{display:flex;align-items:center;gap:8px}}.sequence{{min-width:28px}}.source{{color:#475467!important}}
.method,.status{{padding:2px 7px;border-radius:4px;background:#eef2f6}}.url{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.status{{margin-left:auto}}.api-call small{{float:none;min-width:52px;text-align:right}}
@media(max-width:760px){{.exchange{{grid-template-columns:1fr}}.conversation .message{{max-width:100%}}.source{{display:none}}}}
</style></head><body><main><h1>bk-aidev-agent 本地 E2E</h1>
<section class="card">开始：{html.escape(safe["started_at"])}<br>结束：{html.escape(safe["finished_at"])}<br>
模块：{html.escape(", ".join(safe["modules"]))}<br>鉴权：{html.escape(safe["auth_mode"])}<br>
结果：<b>{report.passed} passed / {report.failed} failed</b><br>接口调用：<b>{len(safe["api_calls"])} 次</b></section>
<h2>会话内容</h2>{conversations}<h2>用例结果</h2>{"".join(rows)}
<h2>完整 API 调用记录（{len(safe["api_calls"])}）</h2>{api_calls}</main></body></html>"""
    html_path = output_dir / "report.html"
    html_path.write_text(document, encoding="utf-8")
    (report_dir / "latest.html").write_text(document, encoding="utf-8")
    return html_path
