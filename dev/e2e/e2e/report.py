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
    coverage: str = ""


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


def _render_capability_overview(cases: list[dict[str, Any]]) -> str:
    module_names = {
        "api": "API 与登录",
        "ai-blueking": "AI 小鲸与智能体对话",
        "message": "数据库与消息服务",
        "metrics": "可观测性",
        "wxbot": "企业微信",
        "runner": "测试基础设施",
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        grouped.setdefault(str(case.get("module", "unknown")), []).append(case)

    cards = []
    for module, module_cases in grouped.items():
        passed = sum(case.get("status") == "passed" for case in module_cases)
        healthy = passed == len(module_cases)
        state_class = "healthy" if healthy else "unhealthy"
        state_text = "功能正常" if healthy else "存在异常"
        scenarios = []
        for case in module_cases:
            case_passed = case.get("status") == "passed"
            icon = "✓" if case_passed else "✗"
            coverage = case.get("coverage") or case.get("name", "")
            error = case.get("error", "")
            error_html = f'<p class="error">{html.escape(str(error))}</p>' if error else ""
            scenarios.append(
                f'<li class="{"ok" if case_passed else "bad"}"><span>{icon}</span><div>'
                f"<b>{html.escape(str(case.get('name', '')))}</b>"
                f"<p>{html.escape(str(coverage))}</p>{error_html}</div>"
                f"<small>{case.get('duration_ms', 0)} ms</small></li>"
            )
        cards.append(
            f'<section class="component-card {state_class}"><header><h3>{html.escape(module_names.get(module, module))}</h3>'
            f"<span>{state_text} · {passed}/{len(module_cases)}</span></header><ul>{''.join(scenarios)}</ul></section>"
        )
    return '<div class="component-grid">' + "".join(cards) + "</div>"


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

    capability_overview = _render_capability_overview(safe["cases"])
    conversations = _render_conversations(safe["conversations"])
    api_calls = _render_api_calls(safe["api_calls"])
    overall_state = "本次覆盖的功能均正常" if report.failed == 0 else "发现功能异常，请查看红色场景"
    overall_class = "healthy" if report.failed == 0 else "unhealthy"
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>bk-aidev-agent E2E report</title><style>
body{{font:14px/1.5 system-ui;margin:0;background:#f5f7fa;color:#17233d}}main{{max-width:1100px;margin:32px auto;padding:0 20px}}
.card,details,.component-card{{background:white;border:1px solid #e5e7eb;border-radius:8px;margin:10px 0;padding:14px}}summary{{cursor:pointer;font-weight:600}}
.passed summary span{{color:#169c51}}.failed summary span,.error{{color:#d4380d}}small{{float:right;color:#7a869a;font-weight:400}}
pre{{overflow:auto;background:#0b1020;color:#d9e2f2;padding:14px;border-radius:6px;white-space:pre-wrap;overflow-wrap:anywhere}}
code{{font-family:ui-monospace}}h2{{margin:28px 0 10px}}h3,h4{{margin:0 0 8px}}.meta,.empty{{color:#667085}}
.conversation .message{{max-width:82%;margin:12px 0;padding:12px 14px;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere}}
.conversation .user{{margin-left:auto;background:#e8f3ff}}.conversation .assistant{{background:#f2f4f7}}
.exchange{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.exchange section{{min-width:0}}
.api-call summary{{display:flex;align-items:center;gap:8px}}.sequence{{min-width:28px}}.source{{color:#475467!important}}
.method,.status{{padding:2px 7px;border-radius:4px;background:#eef2f6}}.url{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.status{{margin-left:auto}}.api-call small{{float:none;min-width:52px;text-align:right}}
.result-banner{{border-left:5px solid #12a150}}.result-banner.unhealthy{{border-left-color:#d4380d}}.result-banner h2{{margin:0 0 4px}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}}.stat{{background:#f7f9fc;padding:10px;border-radius:6px}}
.stat b{{display:block;font-size:22px}}.component-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.component-card{{margin:0}}.component-card header{{display:flex;justify-content:space-between;gap:10px;align-items:center}}
.component-card header span{{color:#168a4a;font-weight:600}}.component-card.unhealthy header span{{color:#d4380d}}
.component-card ul{{list-style:none;margin:12px 0 0;padding:0}}.component-card li{{display:grid;grid-template-columns:24px 1fr auto;gap:8px;padding:10px 0;border-top:1px solid #eef1f5}}
.component-card li>span{{color:#169c51;font-size:18px;font-weight:700}}.component-card li.bad>span{{color:#d4380d}}
.component-card li p{{color:#667085;margin:3px 0 0}}.component-card li small{{float:none;padding-left:8px}}
@media(max-width:760px){{.exchange,.component-grid{{grid-template-columns:1fr}}.stats{{grid-template-columns:1fr 1fr}}.conversation .message{{max-width:100%}}.source{{display:none}}}}
</style></head><body><main><h1>bk-aidev-agent 本地 E2E</h1>
<section class="card result-banner {overall_class}"><h2>{overall_state}</h2>
<span class="meta">✓ 表示该功能在本次本地全链路中实际执行并通过断言；✗ 表示功能未通过；未列出的功能不代表已验证。</span>
<div class="stats"><div class="stat">覆盖组件<b>{len({case["module"] for case in safe["cases"]})}</b></div>
<div class="stat">功能场景<b>{len(safe["cases"])}</b></div><div class="stat">正常<b>{report.passed}</b></div>
<div class="stat">异常<b>{report.failed}</b></div></div><p class="meta">开始：{html.escape(safe["started_at"])}　
结束：{html.escape(safe["finished_at"])}　鉴权：{html.escape(safe["auth_mode"])}　自动化计数：{report.passed} passed / {report.failed} failed</p></section>
<h2>功能健康概览</h2>{capability_overview}<h2>验证证据：会话内容</h2>{conversations}
<h2>诊断证据：完整 API 调用记录（{len(safe["api_calls"])}）</h2>{api_calls}</main></body></html>"""
    html_path = output_dir / "report.html"
    html_path.write_text(document, encoding="utf-8")
    (report_dir / "latest.html").write_text(document, encoding="utf-8")
    return html_path
