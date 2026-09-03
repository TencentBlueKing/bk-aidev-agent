#!/bin/bash

set -euo pipefail

echo "================= Starting WxAiBot WebSocket Worker ================="
exec python bin/manage.py run_wxaibot_ws
