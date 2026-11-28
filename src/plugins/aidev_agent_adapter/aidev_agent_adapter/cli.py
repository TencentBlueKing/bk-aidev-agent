"""本机同步、轮询、ACP Chat 和事件续传入口。凭据仅从环境读取。"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .adapter import Adapter
from .config_sync import ConfigSynchronizer
from .journal import Journal
from .models import Settings
from .platform import PlatformClient


def load_settings(path: Path) -> Settings:
    data = json.loads(path.read_text())
    data["access_token"] = os.environ["AIDEV_ACCESS_TOKEN"]
    data["app_secret"] = os.environ.get("AIDEV_APP_SECRET", "")
    return Settings.model_validate(data)


async def run(args) -> None:
    settings = load_settings(args.config)
    if args.action == "replay":
        journal = Journal(settings.root / "journal", settings.identity)
        try:
            after = args.after
            while batch := journal.replay(args.run_id, after):
                for envelope in batch:
                    print(json.dumps(envelope, ensure_ascii=False), flush=True)
                    after = envelope["sequence"]
        finally:
            journal.close()
        return
    platform = PlatformClient(settings)
    sync = ConfigSynchronizer(settings, platform)
    try:
        if args.action in {"sync", "watch"}:
            while True:
                try:
                    snapshot = await sync.sync()
                    print(
                        json.dumps(
                            {
                                "revision": snapshot.revision,
                                "path": str(snapshot.path),
                                "environment": snapshot.environment,
                            }
                        ),
                        flush=True,
                    )
                except Exception:
                    if args.action != "watch":
                        raise
                    print("Configuration sync failed; previous snapshot retained", file=sys.stderr, flush=True)
                if args.action != "watch":
                    return
                await asyncio.sleep(settings.poll_seconds)
        snapshot = await sync.sync()
        adapter = Adapter(settings, snapshot)
        try:
            if args.action == "chat":
                await adapter.submit(args.run_id, args.thread_id, sys.stdin.read())
            async for envelope in adapter.events(args.run_id, args.after):
                print(json.dumps(envelope, ensure_ascii=False), flush=True)
        finally:
            await adapter.close()
    finally:
        await platform.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="AIDev 配置同步与 ACP / AG-UI 适配")
    parser.add_argument("--config", type=Path, required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("sync")
    sub.add_parser("watch")
    for action in ("chat", "replay"):
        command = sub.add_parser(action)
        command.add_argument("--run-id", required=True)
        command.add_argument("--after", type=int, default=0)
        if action == "chat":
            command.add_argument("--thread-id", required=True)
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception:
        # HTTP 异常、校验异常和引擎异常可能携带凭据，不直接打印原始异常。
        print("Adapter failed; check configuration, platform access and engine availability", file=sys.stderr)
        raise SystemExit(1) from None
