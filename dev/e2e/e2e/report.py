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

MODULE_NAMES = {
    "api": "API 与登录",
    "ai-blueking": "AI 小鲸与智能体对话",
    "message": "数据库与消息服务",
    "metrics": "可观测性",
    "wxbot": "企业微信",
    "runner": "测试基础设施",
}


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
    scenario_id: str = ""


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


def _scenario_anchor(scenario_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", scenario_id).strip("-") or "unknown"


def _index_by_scenario(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    indexed: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        scenario_id = str(item.get("scenario_id", ""))
        if scenario_id:
            indexed.setdefault(scenario_id, []).append(item)
    return indexed


def _render_capability_overview(
    cases: list[dict[str, Any]], conversations: list[dict[str, Any]], api_calls: list[dict[str, Any]]
) -> str:
    conversations_by_scenario = _index_by_scenario(conversations)
    calls_by_scenario = _index_by_scenario(api_calls)
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
            scenario_id = str(case.get("scenario_id") or f"{module}.unknown")
            anchor = _scenario_anchor(scenario_id)
            case_passed = case.get("status") == "passed"
            icon = "✓" if case_passed else "✗"
            coverage = case.get("coverage") or case.get("name", "")
            error = case.get("error", "")
            error_html = f'<p class="error">{html.escape(str(error))}</p>' if error else ""
            conversation_count = len(conversations_by_scenario.get(scenario_id, []))
            api_count = len(calls_by_scenario.get(scenario_id, []))
            scenarios.append(
                f'<li id="health-{anchor}" class="{"ok" if case_passed else "bad"}"><span>{icon}</span><div>'
                f"<b>{html.escape(str(case.get('name', '')))}</b>"
                f"<p>{html.escape(str(coverage))}</p>{error_html}</div>"
                '<div class="scenario-actions">'
                f"<small>{case.get('duration_ms', 0)} ms</small>"
                f'<a href="#evidence-{anchor}">查看证据 · 1 断言 / {conversation_count} 会话 / {api_count} API</a>'
                "</div></li>"
            )
        cards.append(
            f'<section class="component-card {state_class}"><header><h3>{html.escape(MODULE_NAMES.get(module, module))}</h3>'
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
            f"{html.escape(str(call.get('case', '')))}　场景："
            f"<code>{html.escape(str(call.get('scenario_id', '未关联')))}</code></p>{error_html}"
            '<div class="exchange"><section><h4>请求 Headers</h4>'
            f"<pre>{request_headers}</pre><h4>请求 Body</h4><pre>{request_body}</pre></section>"
            "<section><h4>响应 Headers</h4>"
            f"<pre>{response_headers}</pre><h4>响应 Body</h4><pre>{response_body}</pre></section></div></details>"
        )
    return "".join(rows) or '<section class="card empty">本次执行未记录到 HTTP 调用。</section>'


def _render_scenario_evidence(
    cases: list[dict[str, Any]], conversations: list[dict[str, Any]], api_calls: list[dict[str, Any]]
) -> str:
    conversations_by_scenario = _index_by_scenario(conversations)
    calls_by_scenario = _index_by_scenario(api_calls)
    evidence_sections = []
    known_scenarios = set()

    for case in cases:
        module = str(case.get("module", "unknown"))
        module_name = MODULE_NAMES.get(module, module)
        case_name = str(case.get("name", ""))
        scenario_id = str(case.get("scenario_id") or f"{module}.unknown")
        known_scenarios.add(scenario_id)
        anchor = _scenario_anchor(scenario_id)
        related_conversations = conversations_by_scenario.get(scenario_id, [])
        related_calls = calls_by_scenario.get(scenario_id, [])
        case_passed = case.get("status") == "passed"
        state_class = "healthy" if case_passed else "unhealthy"
        state_text = "验证通过" if case_passed else "验证失败"
        coverage = case.get("coverage") or case.get("name", "")
        detail = _pretty(case.get("detail"))
        error = case.get("error", "")
        error_html = f'<p class="error">失败原因：{html.escape(str(error))}</p>' if error else ""
        detail_html = (
            f'<details class="assertion-detail"><summary>查看断言输出</summary><pre>{detail}</pre></details>'
            if detail
            else ""
        )
        conversation_html = ""
        if related_conversations:
            conversation_html = (
                f"<h4>会话证据（{len(related_conversations)}）</h4>{_render_conversations(related_conversations)}"
            )
        api_html = ""
        if related_calls:
            api_html = f"<h4>接口证据（{len(related_calls)}）</h4>{_render_api_calls(related_calls)}"

        evidence_sections.append(
            f'<section id="evidence-{anchor}" class="card scenario-evidence {state_class}">'
            f'<header><div><p class="eyebrow">{html.escape(module_name)}</p>'
            f'<h3>{html.escape(case_name)}</h3></div><span class="evidence-state">{state_text}</span></header>'
            f'<p class="meta">场景标识：<code>{html.escape(scenario_id)}</code></p>'
            '<div class="evidence-counts">'
            "<span>1 项断言</span>"
            f"<span>{len(related_conversations)} 组会话</span><span>{len(related_calls)} 次 API</span>"
            f"<span>{case.get('duration_ms', 0)} ms</span></div>"
            f'<div class="assertion-proof"><b>通过依据</b><p>{html.escape(str(coverage))}</p>{error_html}</div>'
            f"{detail_html}{conversation_html}{api_html}"
            f'<a class="back-link" href="#health-{anchor}">↑ 返回对应健康项</a></section>'
        )

    unmatched_conversations = [
        conversation
        for conversation in conversations
        if str(conversation.get("scenario_id", "")) not in known_scenarios
    ]
    unmatched_calls = [call for call in api_calls if str(call.get("scenario_id", "")) not in known_scenarios]
    if unmatched_conversations or unmatched_calls:
        conversation_html = ""
        if unmatched_conversations:
            conversation_html = (
                f"<h4>会话记录（{len(unmatched_conversations)}）</h4>{_render_conversations(unmatched_conversations)}"
            )
        api_html = ""
        if unmatched_calls:
            api_html = f"<h4>接口记录（{len(unmatched_calls)}）</h4>{_render_api_calls(unmatched_calls)}"
        evidence_sections.append(
            '<section class="card scenario-evidence supporting"><header><div><p class="eyebrow">公共支撑链路</p>'
            '<h3>应用启动与测试基础设施</h3></div><span class="evidence-state">支撑证据</span></header>'
            '<p class="meta">这些记录没有关联到健康场景，不单独证明某个功能正常。</p>'
            f"{conversation_html}{api_html}</section>"
        )

    return "".join(evidence_sections)


def write_report(report: RunReport, report_dir: Path, secrets: tuple[str, ...] = ()) -> Path:
    report.finish()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output_dir = report_dir / stamp
    output_dir.mkdir(parents=True, exist_ok=False)
    safe = redact(asdict(report), secrets)
    json_path = output_dir / "result.json"
    json_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")

    capability_overview = _render_capability_overview(safe["cases"], safe["conversations"], safe["api_calls"])
    scenario_evidence = _render_scenario_evidence(safe["cases"], safe["conversations"], safe["api_calls"])
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
.component-card li p{{color:#667085;margin:3px 0 0}}.component-card li small{{float:none}}.scenario-actions{{text-align:right;min-width:190px}}
.scenario-actions a,.back-link{{display:block;margin-top:5px;color:#1769aa;text-decoration:none;font-size:12px}}.scenario-actions a:hover,.back-link:hover{{text-decoration:underline}}
.scenario-evidence{{scroll-margin-top:20px;border-left:5px solid #12a150}}.scenario-evidence.unhealthy{{border-left-color:#d4380d}}
.scenario-evidence.supporting{{border-left-color:#8091a7}}.scenario-evidence:target,.component-card li:target{{box-shadow:0 0 0 3px #b7dcff}}
.scenario-evidence>header{{display:flex;justify-content:space-between;align-items:center;gap:12px}}.eyebrow{{margin:0;color:#667085;font-size:12px}}
.evidence-state{{font-weight:700;color:#168a4a}}.unhealthy .evidence-state{{color:#d4380d}}.supporting .evidence-state{{color:#667085}}
.evidence-counts{{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}}.evidence-counts span{{background:#eef4fa;border-radius:999px;padding:4px 9px;font-size:12px}}
.assertion-proof{{background:#f6fbf8;border:1px solid #d7eee0;border-radius:7px;padding:11px 12px;margin:10px 0}}.assertion-proof p{{margin:4px 0 0}}
.assertion-detail{{padding:10px;margin:10px 0}}.scenario-evidence h4{{margin-top:18px}}
@media(max-width:760px){{.exchange,.component-grid{{grid-template-columns:1fr}}.stats{{grid-template-columns:1fr 1fr}}.conversation .message{{max-width:100%}}.source{{display:none}}.component-card li{{grid-template-columns:24px 1fr}}.scenario-actions{{grid-column:2;text-align:left}}}}
</style></head><body><main><h1>bk-aidev-agent 本地 E2E</h1>
<section class="card result-banner {overall_class}"><h2>{overall_state}</h2>
<span class="meta">✓ 表示该功能在本次本地全链路中实际执行并通过断言；点击“查看证据”可定位到同一场景的断言、会话和 API；未列出的功能不代表已验证。</span>
<div class="stats"><div class="stat">覆盖组件<b>{len({case["module"] for case in safe["cases"]})}</b></div>
<div class="stat">功能场景<b>{len(safe["cases"])}</b></div><div class="stat">正常<b>{report.passed}</b></div>
<div class="stat">异常<b>{report.failed}</b></div></div><p class="meta">开始：{html.escape(safe["started_at"])}　
结束：{html.escape(safe["finished_at"])}　鉴权：{html.escape(safe["auth_mode"])}　自动化计数：{report.passed} passed / {report.failed} failed</p></section>
<h2>功能健康概览</h2>{capability_overview}
<h2>场景验证证据</h2><p class="meta">全部 {len(safe["api_calls"])} 次 API 调用均按场景归档；公共启动调用单独列出。</p>
{scenario_evidence}</main></body></html>"""
    html_path = output_dir / "report.html"
    html_path.write_text(document, encoding="utf-8")
    (report_dir / "latest.html").write_text(document, encoding="utf-8")
    return html_path
