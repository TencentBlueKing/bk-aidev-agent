#!/usr/bin/env bash
# Dual-process supervisor: local craw gateway + gunicorn.
# The kernel entrypoint comes from the base image. Do not hard-code hostnames.
set -euo pipefail

OC_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
OC_PID=""
WEB_PID=""
EGRESS_PID=""
APP_IDENTITY_PID=""
READY_URL="http://127.0.0.1:${OC_PORT}/healthz"
READY_ATTEMPTS="${BKAI_OPENCLAW_READY_ATTEMPTS:-90}"
READY_INTERVAL="${BKAI_OPENCLAW_READY_INTERVAL:-2}"
KERNEL_ENTRYPOINT="${BKAI_CRAW_ENTRYPOINT:-/usr/local/bin/docker-entrypoint.sh}"

cleanup() {
  trap - TERM INT
  echo "[craw] shutting down child processes" >&2
  if [ -n "${WEB_PID}" ]; then
    kill -TERM "${WEB_PID}" 2>/dev/null || true
  fi
  if [ -n "${OC_PID}" ]; then
    kill -TERM "${OC_PID}" 2>/dev/null || true
  fi
  if [ -n "${EGRESS_PID}" ]; then
    kill -TERM "${EGRESS_PID}" 2>/dev/null || true
  fi
  if [ -n "${APP_IDENTITY_PID}" ]; then
    kill -TERM "${APP_IDENTITY_PID}" 2>/dev/null || true
  fi
  wait || true
}

is_web=0
if [[ "$*" == *gunicorn* ]]; then
  is_web=1
fi

if [ "${is_web}" -ne 1 ]; then
  exec "$@"
fi

if [ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ]; then
  if [ -n "${BKAI_CRAW_API_KEY:-}" ]; then
    export OPENCLAW_GATEWAY_TOKEN="${BKAI_CRAW_API_KEY}"
  else
    export OPENCLAW_GATEWAY_TOKEN="$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    echo "[craw] generated an ephemeral loopback gateway token"
  fi
fi

if [ ! -x "${KERNEL_ENTRYPOINT}" ]; then
  echo "[craw] FATAL: kernel entrypoint not found: ${KERNEL_ENTRYPOINT}" >&2
  exit 1
fi

export BKAI_CRAW_API_URL="${BKAI_CRAW_API_URL:-http://127.0.0.1:${OC_PORT}}"
export OPENCLAW_GATEWAY_PORT="${OC_PORT}"
export BKAI_CRAW_BACKEND="${BKAI_CRAW_BACKEND:-openclaw}"
export OPENCLAW_SUPERVISOR_MODE="${OPENCLAW_SUPERVISOR_MODE:-external}"
CRAW_AGENT_CODE="${BKAI_AGENT:-${BKPAAS_APP_ID:-${BK_APP_CODE:-}}}"
export BKAI_MCP_EGRESS_PORT="${BKAI_MCP_EGRESS_PORT:-18787}"
export BKAI_MCP_EGRESS_URL="${BKAI_MCP_EGRESS_URL:-http://127.0.0.1:${BKAI_MCP_EGRESS_PORT}}"
export BKAI_MCP_EGRESS_ROUTES="${BKAI_MCP_EGRESS_ROUTES:-/tmp/craw-mcp-routes.json}"

if [ -z "${CRAW_AGENT_CODE}" ] || [ ! -x /app/.venv/bin/python ]; then
  echo "[craw] FATAL: current application identity is unavailable" >&2
  exit 1
fi
for required in AIDEV_GATEWAY_NAME BK_APIGW_STAGE BKAI_AIDEV_APP_UPSTREAM_ORIGIN; do
  if [ -z "${!required:-}" ]; then
    echo "[craw] FATAL: missing injected runtime setting: ${required}" >&2
    exit 1
  fi
done

# 启动配置走 PaaS 注入的 app_code/app_secret；不要求、不落盘用户或共享 API token。
BKAI_AGENT="${CRAW_AGENT_CODE}" /app/.venv/bin/python /app/deploy/apply-agent-config.py
# 基座看到 token 会额外执行 bkai mcp/agent apply；应用态装配已完成，显式清理避免误用手工 token。
unset BKAI_AGENT BKAI_AIDEV_API_KEY
/app/.venv/bin/python /app/deploy/app-identity-egress.py &
APP_IDENTITY_PID=$!

if [ "${BKAI_MCP_EGRESS_ENABLED:-1}" = "1" ]; then
  echo "[craw] starting MCP egress on 127.0.0.1:${BKAI_MCP_EGRESS_PORT}"
  if [ -x /app/.venv/bin/python ]; then
    /app/.venv/bin/python -m aidev_agent.packages.craw.mcp_egress --port "${BKAI_MCP_EGRESS_PORT}" &
    EGRESS_PID=$!
  fi
fi

# 在内核启动前完成 MCP URL → 用户态 egress 改写，避免首轮加载到直连上游。
if [ -n "${EGRESS_PID}" ]; then
  CONFIG_CANDIDATE="${OPENCLAW_CONFIG_PATH:-${HOME}/.openclaw/openclaw.json}"
  if [ -f "${CONFIG_CANDIDATE}" ]; then
    echo "[craw] rewriting MCP servers to egress via ${CONFIG_CANDIDATE}"
    /app/.venv/bin/python -m aidev_agent.packages.craw.mcp_egress \
      --rewrite-only --config "${CONFIG_CANDIDATE}" --port "${BKAI_MCP_EGRESS_PORT}" || \
      echo "[craw] WARN: MCP egress rewrite failed" >&2
  fi
fi

trap 'cleanup; exit 143' TERM
trap 'cleanup; exit 130' INT

echo "[craw] starting kernel on 127.0.0.1:${OC_PORT}"
"${KERNEL_ENTRYPOINT}" &
OC_PID=$!

ready=0
for _ in $(seq 1 "${READY_ATTEMPTS}"); do
  if ! kill -0 "${OC_PID}" 2>/dev/null; then
    echo "[craw] FATAL: kernel exited before healthz became ready" >&2
    wait "${OC_PID}" || true
    exit 1
  fi
  if command -v curl >/dev/null 2>&1 && curl -fsS "${READY_URL}" >/dev/null 2>&1; then
    ready=1
    echo "[craw] kernel healthz is ready"
    break
  fi
  sleep "${READY_INTERVAL}"
done

if [ "${ready}" -ne 1 ]; then
  echo "[craw] FATAL: kernel healthz not ready after ${READY_ATTEMPTS} attempts" >&2
  cleanup
  exit 1
fi

# OpenClaw scans its native managed Skills directory per run. Sync after healthz so
# a missing or malformed optional Skill never takes down the web process.
(BKAI_CRAW_SKILLS_ONLY=1 /app/.venv/bin/python /app/deploy/apply-agent-config.py || \
  echo "[craw] WARN: Skill sync failed; continuing without new Skills" >&2) &

if [ -x /app/.venv/bin/python ]; then
  (cd /app && /app/.venv/bin/python bin/manage.py migrate --noinput) || \
    echo "[craw] migrate fallback failed; continuing" >&2
  (cd /app && /app/.venv/bin/python bin/manage.py collectstatic --noinput) || \
    echo "[craw] collectstatic failed; /chat-window/ may not render" >&2
fi

echo "[craw] starting web process: $*"
"$@" &
WEB_PID=$!

while kill -0 "${OC_PID}" 2>/dev/null && kill -0 "${WEB_PID}" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "${OC_PID}" 2>/dev/null; then
  echo "[craw] FATAL: kernel exited; stopping gunicorn" >&2
else
  echo "[craw] FATAL: gunicorn exited; stopping kernel" >&2
fi
cleanup
exit 1
