# -*- coding: utf-8 -*-
"""
Gunicorn 配置文件
支持通过环境变量自定义配置
"""

import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 服务器绑定地址和端口
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# 工作进程数
workers = int(os.getenv("GUNICORN_WORKERS", "2"))

# 工作进程类型
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")

# 每个工作进程的线程数
threads = int(os.getenv("GUNICORN_THREADS", "64"))

# 请求超时时间
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))

# 最大请求数（达到后重启工作进程）
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))

# 最大请求数的随机偏移
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

# 预加载应用
preload_app = os.getenv("GUNICORN_PRELOAD_APP", "False").lower() == "true"

# 日志配置
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")  # "-" 表示 stdout
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")    # "-" 表示 stderr
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# 进程名称
proc_name = os.getenv("GUNICORN_PROC_NAME", "ai-hpclienttools")

# 用户和组（生产环境可能需要）
user = os.getenv("GUNICORN_USER", None)
group = os.getenv("GUNICORN_GROUP", None)

# 临时目录
tmp_upload_dir = os.getenv("GUNICORN_TMP_UPLOAD_DIR", None)

# 保持连接时间
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "2"))

# 最大客户端连接数
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", "1000"))

# 静态文件处理（如果需要）
# 注意：生产环境建议使用 Nginx 等反向代理处理静态文件
# sendfile = True

# 安全相关
limit_request_line = int(os.getenv("GUNICORN_LIMIT_REQUEST_LINE", "4094"))
limit_request_fields = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELDS", "100"))
limit_request_field_size = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELD_SIZE", "8190"))

# 钩子函数
def on_starting(server):
    """服务器启动时调用"""
    server.log.info("AI HPClientTools 服务正在启动...")

def on_reload(server):
    """服务器重载时调用"""
    server.log.info("AI HPClientTools 服务正在重载...")

def worker_int(worker):
    """工作进程收到 SIGINT 信号时调用"""
    worker.log.info("工作进程 %s 收到中断信号", worker.pid)

def pre_fork(server, worker):
    """工作进程 fork 前调用"""
    server.log.info("工作进程 %s 即将启动", worker.pid)

def post_fork(server, worker):
    """工作进程 fork 后调用"""
    server.log.info("工作进程 %s 已启动", worker.pid)

def worker_abort(worker):
    """工作进程异常退出时调用"""
    worker.log.info("工作进程 %s 异常退出", worker.pid)