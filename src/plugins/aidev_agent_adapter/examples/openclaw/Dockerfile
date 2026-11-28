FROM node:24-bookworm AS engine
ARG OPENCLAW_VERSION=2026.11.6
ARG NPM_CONFIG_REGISTRY=https://registry.npmjs.org
RUN npm install --global openclaw@${OPENCLAW_VERSION} && npm install --prefix /app/otel @openclaw/diagnostics-otel@${OPENCLAW_VERSION} && npm cache clean --force

FROM python:3.11-slim-bookworm
COPY --from=engine /app/otel /app/otel
COPY --from=engine /usr/local/bin/node /usr/local/bin/node
COPY --from=engine /usr/local/lib/node_modules/openclaw /app/runtime/openclaw
RUN ln -s /app/runtime/openclaw/openclaw.mjs /usr/local/bin/openclaw
WORKDIR /opt/adapter
COPY pyproject.toml readme.md ./
COPY aidev_agent_adapter/ ./aidev_agent_adapter/
RUN python -m venv /app/.venv && /app/.venv/bin/pip install --no-cache-dir . \
    && /app/.venv/bin/python -m aidev_agent_adapter.openclaw_trace_bridge /app/runtime/openclaw
COPY examples/openclaw/demo.py /opt/adapter/demo.py
RUN useradd --create-home adapter && install -d -o adapter -g adapter -m 700 /var/lib/aidev-adapter /app/workspace \
    && install -d /app/.storage/agent /app/.storage/user /app/.storage/session
USER adapter
WORKDIR /app/workspace
ENV OPENCLAW_STATE_DIR=/app/.storage/user/state
ENTRYPOINT ["/app/.venv/bin/aidev-openclaw-adapter"]
CMD ["--config","/run/aidev/config.json"]
