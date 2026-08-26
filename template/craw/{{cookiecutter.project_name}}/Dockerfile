# Overlay this plugin onto a craw kernel image.
# The base image is supplied at generate time. Do not bake a private registry,
# image digest, or environment-specific hostname into the public template.
ARG CRAW_BASE_IMAGE={{ cookiecutter.craw_base_image }}
FROM ${CRAW_BASE_IMAGE}

USER root
WORKDIR /app

# The OpenClaw base provides Python 3.11 and the package index policy. Install
# the plugin into an isolated interpreter because the base image only contains
# the craw kernel; it does not provide aidev-agent/aidev-bkplugin or gunicorn.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_DEFAULT_INDEX=${PIP_INDEX_URL} \
    UV_LINK_MODE=copy \
    UV_NO_PROGRESS=1 \
    UV_HTTP_TIMEOUT=120 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    PATH=/app/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN pip3 install --no-cache-dir --break-system-packages "uv==0.11.24"

COPY requirements.txt /app/requirements.txt
RUN uv python install 3.11.10 \
    && uv venv /app/.venv --python 3.11.10 \
    && uv pip install --python /app/.venv/bin/python --no-progress -r /app/requirements.txt

COPY . /app

RUN chmod 0755 /app/deploy/craw-supervisor.sh /app/bin/manage.py /app/bin/pre_release.sh \
    && mkdir -p /data/craw \
    && chmod 1777 /data/craw \
    && chown -R bkmonitor:bkmonitor /app /data/craw /opt/uv-python

USER bkmonitor

# tini must be PID 1. PaaS may replace ENTRYPOINT with procCommand from app_desc.yml.
ENTRYPOINT ["tini", "--"]
CMD ["bash", "/app/deploy/craw-supervisor.sh", "gunicorn", "bk_plugin_runtime.wsgi", "--bind", "0.0.0.0:5000", "--timeout", "300"]
