#!/usr/bin/env bash
# craw 本地模拟 · 插件集成变体一键验证：
# 业务插件（Django）→ SDK craw 接管 CHAT → OpenClaw。
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE="${ENV_FILE:-./agent.env}"
PORT="${PLUGIN_PORT_HOST:-8000}"
COMPOSE=(docker compose -f docker-compose.plugin.yml --env-file "${ENV_FILE}")

echo "==> docker compose up（plugin 变体, env-file: ${ENV_FILE}）"
"${COMPOSE[@]}" up -d --wait

echo "==> 等待 plugin gunicorn 就绪"
for _ in $(seq 1 30); do
  curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/bk_plugin/meta.json" 2>/dev/null && break
  sleep 2
done

echo "==> 核验 craw 已接管 CHAT（看启动日志）"
# 先落变量再 grep：pipefail 下 grep -m1 提前关管道会让 compose logs 吃 SIGPIPE 误报失败
PLUGIN_LOGS="$("${COMPOSE[@]}" logs plugin 2>&1)"
grep -m1 "CrawCompletionAgent 已接管" <<<"${PLUGIN_LOGS}" || {
  echo "FAIL: 未见 craw 接管日志"; exit 1; }

echo "==> 整链非流式（经插件 /chat_completion/）"
curl -sS "http://127.0.0.1:${PORT}/bk_plugin/plugin_api/chat_completion/" \
  -H "X-BKAIDEV-USER: ${SIM_USERNAME:-demo-user}" -H "Content-Type: application/json" \
  -d '{"input":"请只回复一个单词：pong","execute_kwargs":{"stream":false}}'
echo

echo "==> 整链流式（AG-UI 事件）"
curl -sS -N --max-time 300 "http://127.0.0.1:${PORT}/bk_plugin/plugin_api/chat_completion/" \
  -H "X-BKAIDEV-USER: ${SIM_USERNAME:-demo-user}" -H "Content-Type: application/json" \
  -d '{"input":"说三个字","execute_kwargs":{"stream":true}}' | head -20

echo "ALL PASS (plugin)"
