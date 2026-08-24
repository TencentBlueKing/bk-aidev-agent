# Overlay this plugin onto a craw kernel image.
# The base image is supplied at generate/build time. Do not bake a private
# registry, image digest, or environment-specific hostname into this file.
ARG CRAW_BASE_IMAGE={{ cookiecutter.craw_base_image }}
FROM ${CRAW_BASE_IMAGE}

USER root
WORKDIR /app

COPY . /app

RUN chmod 0755 /app/deploy/craw-supervisor.sh /app/bin/manage.py /app/bin/pre_release.sh \
    && mkdir -p /data/craw \
    && chmod 1777 /data/craw

# tini must be PID 1. PaaS may replace ENTRYPOINT with procCommand from app_desc.yml.
ENTRYPOINT ["tini", "--"]
CMD ["bash", "/app/deploy/craw-supervisor.sh", "gunicorn", "bk_plugin_runtime.wsgi", "--bind", "0.0.0.0:5000", "--timeout", "300"]
