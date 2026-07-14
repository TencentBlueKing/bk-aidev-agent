#!/usr/bin/env bash
# craw 本地模拟 · Hermes 变体一键验证（场景脚本与 openclaw 变体共用）。
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE="${ENV_FILE:-./agent.env}"
PY="${SIM_PYTHON:-/app/.venv/bin/python}"
COMPOSE=(docker compose -f docker-compose.hermes.yml --env-file "${ENV_FILE}")

echo "==> docker compose up（hermes 变体, env-file: ${ENV_FILE}）"
"${COMPOSE[@]}" up -d --wait

echo "==> 场景 1：agent --localhost--> craw(hermes api_server)"
"${COMPOSE[@]}" exec -T agent "${PY}" /sdk-src/examples/craw_local_sim/scenario_chat.py

echo "==> 场景 2：agent --read/write--> craw（周期任务）"
"${COMPOSE[@]}" exec -T agent "${PY}" /sdk-src/examples/craw_local_sim/scenario_sync.py

echo "==> craw 侧核验 SOUL.md 落盘"
"${COMPOSE[@]}" exec -T hermes head -3 /craw-home/SOUL.md

echo "ALL PASS (hermes)"
