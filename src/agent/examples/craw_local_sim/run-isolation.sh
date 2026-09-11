#!/usr/bin/env bash
# MCP 用户 Token 隔离实测：bkai-cli 池模式反代 + REAL/FAKE 双身份。
#
# 前提：
#   1. ./run-hermes.sh 已起 hermes 变体（compose 已挂 /bkai-cli 并透传双 token env）；
#   2. 凭据文件含 REAL_MCP_ACCESS_TOKEN / FAKE_MCP_ACCESS_TOKEN（值不入库、不回显）。
#
# 判定：REAL 身份 mcp-probe = accessible 且 FAKE = rejected → ISOLATION PASS。
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE="${ENV_FILE:-./agent.env}"
ENTRY="${POOL_ENTRY_TOKEN:-pool-entry-token}"
AGENT_CODE="${POOL_AGENT:?请设置 POOL_AGENT=<AIDEV agent code>（池模式反代用）}"
COMPOSE=(docker compose -f docker-compose.hermes.yml --env-file "${ENV_FILE}")

echo "==> 确保池模式反代在跑（容器内 8788，日志 /tmp/pool.log）"
if ! "${COMPOSE[@]}" exec -T hermes sh -c 'curl -s -o /dev/null --max-time 3 http://127.0.0.1:8788/' 2>/dev/null; then
  "${COMPOSE[@]}" exec -d -e ENTRY="${ENTRY}" -e AGENT_CODE="${AGENT_CODE}" hermes sh -c '
    mkdir -p /tmp/bkai-shim
    printf "#!/bin/sh\nexec node /bkai-cli/bin/bkai.js \"\$@\"\n" > /tmp/bkai-shim/bkai
    chmod +x /tmp/bkai-shim/bkai
    export PATH=/tmp/bkai-shim:$PATH
    exec node /bkai-cli/bin/bkai.js hermes proxy expose --pool --agent "$AGENT_CODE" \
      --aidev-token "$BKAI_AIDEV_API_KEY" --auth-token "$ENTRY" --port 8788 > /tmp/pool.log 2>&1'
  sleep 6
fi

echo "==> 双身份 chat（首次 provision 内核，可能 1-2 分钟；对话不因身份 token 无效而挂）"
"${COMPOSE[@]}" exec -T -e ENTRY="${ENTRY}" hermes sh -c '
for pair in "REAL:$REAL_MCP_ACCESS_TOKEN" "FAKE:$FAKE_MCP_ACCESS_TOKEN"; do
  name="${pair%%:*}"; tok="${pair#*:}"
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 240 -X POST http://127.0.0.1:8788/v1/chat/completions \
    -H "Authorization: Bearer $ENTRY" -H "X-Bkai-Access-Token: $tok" -H "Content-Type: application/json" \
    -d "{\"model\":\"hermes-agent\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"stream\":false}")
  echo "$name chat -> HTTP $code"
done'

echo "==> 双身份 mcp-probe（隔离判定）"
real=$("${COMPOSE[@]}" exec -T -e ENTRY="${ENTRY}" hermes sh -c \
  'curl -s --max-time 20 -X POST http://127.0.0.1:8788/api/v1/bkai/mcp-probe \
     -H "Authorization: Bearer $ENTRY" -H "X-Bkai-Access-Token: $REAL_MCP_ACCESS_TOKEN"')
fake=$("${COMPOSE[@]}" exec -T -e ENTRY="${ENTRY}" hermes sh -c \
  'curl -s --max-time 20 -X POST http://127.0.0.1:8788/api/v1/bkai/mcp-probe \
     -H "Authorization: Bearer $ENTRY" -H "X-Bkai-Access-Token: $FAKE_MCP_ACCESS_TOKEN"')
echo "REAL -> ${real}"
echo "FAKE -> ${fake}"

echo "==> token 不落盘核验（每身份 config.yaml 只应有 X-Bkai-Egress-Key）"
"${COMPOSE[@]}" exec -T hermes python3 - <<'PY'
import glob, yaml
for home in sorted(glob.glob("/home/bkmonitor/.bkai/hermes-pool/*/")):
    try:
        d = yaml.safe_load(open(home + "config.yaml"))
    except Exception:
        continue
    for name, c in list((d.get("mcp_servers") or {}).items())[:1]:
        keys = sorted((c.get("headers") or {}).keys())
        assert "X-Bkapi-Authorization" not in keys, f"{home}: 用户 token 落盘了!"
        print(home.split("/")[-2], name, "->", c.get("url"), "| headers键:", keys)
PY

grep -q '"verdict":"accessible"' <<<"${real}" || { echo "FAIL: REAL 身份未通过"; exit 1; }
grep -q '"verdict":"rejected"' <<<"${fake}" || { echo "FAIL: FAKE 身份未被拒"; exit 1; }
echo "ISOLATION PASS"
