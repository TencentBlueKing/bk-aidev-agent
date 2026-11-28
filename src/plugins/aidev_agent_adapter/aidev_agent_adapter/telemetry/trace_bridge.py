"""Install the request-scoped ACP to Gateway trace bridge for the pinned OpenClaw image."""

import argparse
import json
from pathlib import Path


def install(root: Path) -> None:
    if json.loads((root / "package.json").read_text())["version"] != "2026.11.6":
        raise ValueError("Review the ACP and Gateway request formats before upgrading OpenClaw")

    # This release accepts traceparent on a Gateway request envelope, but its ACP
    # client drops prompt metadata. Preserve it on this chat.send RPC alone.
    replacements = [
        (
            "server-CDUXLTiq.mjs",
            'this.gateway.request("chat.send", n, { timeoutMs: null })',
            'this.gateway.request("chat.send", n, { timeoutMs: null, traceparent: e._meta?.traceparent })',
        ),
        (
            "client-cecYKgQa.mjs",
            "method: t,\n\t\t\t\t\tparams: n\n\t\t\t\t});",
            'method: t,\n\t\t\t\t\ttraceparent: t === "chat.send" ? r?.traceparent : undefined,\n\t\t\t\t\tparams: n\n\t\t\t\t});',
        ),
    ]
    changes = {}
    for name, old, new in replacements:
        path = root / "dist" / name
        source = path.read_text()
        if source.count(old) != 1:
            raise ValueError(f"Unexpected OpenClaw request implementation in {name}")
        changes[path] = source.replace(old, new)
    for path, source in changes.items():
        path.write_text(source)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    install(parser.parse_args().root)
