from __future__ import annotations

import os
import socket
import time
import urllib.error
import urllib.request


def main() -> None:
    targets = [
        ("Redis", "127.0.0.1", 16379),
        ("RabbitMQ AMQP", "127.0.0.1", 25672),
        ("RabbitMQ management", "127.0.0.1", 15673),
    ]
    if os.getenv("E2E_DB", "sqlite").strip().lower() == "mysql":
        targets.insert(0, ("MySQL", "127.0.0.1", 13306))
    deadline = time.monotonic() + 120
    pending = list(targets)
    while pending and time.monotonic() < deadline:
        for target in pending[:]:
            _, host, port = target
            try:
                with socket.create_connection((host, port), timeout=1):
                    pending.remove(target)
            except OSError:
                pass
        if pending:
            time.sleep(1)
    if pending:
        names = ", ".join(item[0] for item in pending)
        raise SystemExit(f"local E2E dependencies did not become ready: {names}")
    health = urllib.request.Request(
        "http://127.0.0.1:15673/api/health/checks/alarms",
        headers={"Authorization": "Basic YWlkZXY6YWlkZXYtZTJl"},
    )
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=2) as response:
                if response.status == 200:
                    break
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    else:
        raise SystemExit("RabbitMQ management API did not become healthy")
    print("Local E2E storage dependencies are accepting connections.")


if __name__ == "__main__":
    main()
