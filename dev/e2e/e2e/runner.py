from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from .app import ManagedApp
from .checks import Checks
from .config import Config, configured_identity
from .mock_remote import RemoteMock
from .report import CaseResult, RunReport, write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bk-aidev-agent local E2E modules")
    parser.add_argument("--modules", default="", help="comma separated modules or all")
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.headless is not None:
        os.environ["E2E_HEADLESS"] = "true" if args.headless else "false"
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    fallback_root = Path(__file__).resolve().parents[3]
    report = RunReport(started, [])
    report_dir = fallback_root / "dev/e2e/reports"
    secrets: tuple[str, ...] = ()
    mock = None
    app = None
    try:
        config = Config.from_env(args.modules)
        report.modules = list(config.modules)
        report_dir = config.report_dir
        identity = configured_identity()
        report.auth_mode = identity.mode
        secrets = (identity.access_token, os.getenv("BKPAAS_APP_SECRET", ""), os.getenv("RABBITMQ_PASSWORD", ""))
        parsed = urlparse(config.mock_url)
        mock = RemoteMock(parsed.hostname or "127.0.0.1", parsed.port or 80, identity.username)
        mock.start()
        app = ManagedApp(config, identity)
        app.start()
        Checks(config, identity, report).run()
    except Exception as error:
        report.cases.append(
            CaseResult("runner", "基础设施与执行器", "failed", 0, {"traceback": traceback.format_exc()}, str(error))
        )
    finally:
        if app:
            app.close()
        if mock:
            mock.close()
        html_path = write_report(report, report_dir, secrets)
        print(f"E2E report: {html_path}")
        print(f"Result: {report.passed} passed / {report.failed} failed")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
