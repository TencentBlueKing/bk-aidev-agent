# Quickstart

## 1. 本地快速启动

### 1.1 配置环境

执行下面的脚本,创建虚拟环境&安装依赖

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env_tpl .env
```

根据实际情况,更新`.env`文件末尾对应的`BKPAAS_APP_SECRET`.

### 1.2 启动服务并测试

执行下面脚本本地启动服务,即可开始测试

```bash
source .env
python bin/manage.py migrate
python bin/manage.py runserver 0.0.0.0:5000
```
