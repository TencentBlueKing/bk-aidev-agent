FROM python:3.11.10-bullseye

COPY requirements.txt requirements.txt

RUN sed -i "s@http://deb.debian.org/debian@http://mirrors.tencent.com/debian@g" /etc/apt/sources.list && \
  apt update && apt install -y vim-tiny && \
  mkdir -p /app && \
  pip config set global.index-url http://mirrors.tencent.com/pypi/simple/ && \
  pip config set global.trusted-host mirrors.tencent.com && \
  pip config set global.root-user-action ignore && \
  pip install --no-cache-dir -r requirements.txt && \
  rm -rf /tmp/*

COPY . /app

WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV DJANGO_SETTINGS_MODULE=bk_plugin.patch.plugin

# 暴露端口
EXPOSE 8000

# 启动命令：使用 Gunicorn 启动应用，支持配置文件
CMD ["gunicorn", "bk_plugin_runtime.wsgi", "-c", "gunicorn.conf.py"]