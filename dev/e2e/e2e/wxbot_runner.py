"""Run the wxbot management command with local WebSocket SDK compatibility."""

from aibot import ws as aibot_ws
from django.core.management import execute_from_command_line


def main() -> None:
    # SDK 1.0.2 always passes a TLS context; the local E2E server uses ws://.
    aibot_ws._SSL_CONTEXT = None
    execute_from_command_line(["bin/manage.py", "run_wxaibot_ws"])


if __name__ == "__main__":
    main()
