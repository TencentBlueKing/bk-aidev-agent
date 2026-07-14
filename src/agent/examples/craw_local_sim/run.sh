#!/usr/bin/env bash
# craw 本地模拟一键验证：起容器 → 场景1（localhost 对话）→ 场景2（周期读写）。
# 凭据经 --env-file 注入（默认取 ./agent.env，参照 agent.env.example 填写；可用 ENV_FILE 覆盖）。
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE="${ENV_FILE:-./agent.env}"
# AGENT_IMAGE 镜像的依赖装在 /app/.venv（系统 python3 无 SDK 依赖）
PY="${SIM_PYTHON:-/app/.venv/bin/python}"

echo "==> docker compose up（env-file: ${ENV_FILE}）"
docker compose --env-file "${ENV_FILE}" up -d --wait

echo "==> 场景 1：agent --localhost--> craw"
docker compose --env-file "${ENV_FILE}" exec -T agent "${PY}" /sdk-src/examples/craw_local_sim/scenario_chat.py

echo "==> 场景 2：agent --read/write--> craw（周期任务）"
docker compose --env-file "${ENV_FILE}" exec -T agent "${PY}" /sdk-src/examples/craw_local_sim/scenario_sync.py

echo "==> craw 侧核验 SOUL.md 落盘"
docker compose --env-file "${ENV_FILE}" exec -T openclaw head -3 /workspace/SOUL.md

echo "ALL PASS"
