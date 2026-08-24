#!/usr/bin/env bash
# Dual-process supervisor: local craw gateway + gunicorn.
# The kernel entrypoint comes from the base image. Do not hard-code hostnames.
set -euo pipefail

OC_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
OC_PID=""
WEB_PID=""
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
  wait || true
}

is_web=0
if [[ "$*" == *gunicorn* ]]; then
  is_web=1
fi

if [ "${is_web}" -ne 1 ]; then
  exec "$@"
fi

if [ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ] && [ -z "${BKAI_CRAW_API_KEY:-}" ]; then
  echo "[craw] FATAL: web mode requires OPENCLAW_GATEWAY_TOKEN or BKAI_CRAW_API_KEY" >&2
  exit 1
fi

if [ ! -x "${KERNEL_ENTRYPOINT}" ]; then
  echo "[craw] FATAL: kernel entrypoint not found: ${KERNEL_ENTRYPOINT}" >&2
  exit 1
fi

export BKAI_CRAW_API_URL="${BKAI_CRAW_API_URL:-http://127.0.0.1:${OC_PORT}}"
export OPENCLAW_GATEWAY_PORT="${OC_PORT}"
export BKAI_CRAW_BACKEND="${BKAI_CRAW_BACKEND:-openclaw}"

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
