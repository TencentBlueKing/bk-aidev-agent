from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

SENSITIVE_KEY = re.compile(r"(token|secret|password|cookie|authorization)", re.I)


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
        return result
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
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>bk-aidev-agent E2E report</title><style>
body{{font:14px/1.5 system-ui;margin:0;background:#f5f7fa;color:#17233d}}main{{max-width:1100px;margin:32px auto;padding:0 20px}}
.card,details{{background:white;border:1px solid #e5e7eb;border-radius:8px;margin:10px 0;padding:14px}}summary{{cursor:pointer;font-weight:600}}
.passed summary span{{color:#169c51}}.failed summary span,.error{{color:#d4380d}}small{{float:right;color:#7a869a;font-weight:400}}
pre{{overflow:auto;background:#0b1020;color:#d9e2f2;padding:14px;border-radius:6px;white-space:pre-wrap}}code{{font-family:ui-monospace}}
</style></head><body><main><h1>bk-aidev-agent 本地 E2E</h1>
<section class="card">开始：{html.escape(safe["started_at"])}<br>结束：{html.escape(safe["finished_at"])}<br>
模块：{html.escape(", ".join(safe["modules"]))}<br>鉴权：{html.escape(safe["auth_mode"])}<br>
结果：<b>{report.passed} passed / {report.failed} failed</b></section>{"".join(rows)}</main></body></html>"""
    html_path = output_dir / "report.html"
    html_path.write_text(document, encoding="utf-8")
    (report_dir / "latest.html").write_text(document, encoding="utf-8")
    return html_path
