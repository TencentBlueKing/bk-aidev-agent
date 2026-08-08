# BK AIDev 平台

## 开发指南

### 初始化
1. 确认 uv 版本
    ```bash
    $ uv --version
    uv 0.7.14 (e7f596711 2025-06-23)
    ```
   
2. 初始化项目环境（虚拟环境位于项目根目录 `.venv` 下），此步骤将始化本地`pre-commit`组件
    ```bash
    $ make
    ```

### 依赖包管理
1. `AIDev` 通过 `uv` 管理项目依赖，不同的模块需要通过 `Group` 管理
   ```bash
   # 平台依赖
   uv add {package_name}~=1.0.0
   # 开发环境依赖
   uv add {package_name}~=1.0.0 -- dev
   ```
2. 可以通过以下命令导出依赖对应的 `requirements.txt`
   ```bash
   make requirements.txt
   ```

### 单元测试

可通过`.env`中配置项目所需的环境变量

1. 查看单测情况
    ```bash
    $ make test
    ```
2. 查看单测覆盖情况
    ```bash
    $ make ci-test
    ```
3. 可以通过`path`参数查看某个模块的单测情况
    ```bash
    $ make test path=./tests/xxx/
    ```

4. 如需指定网关或指定环境,可以配置环境变量`AIDEV_GATEWAY_NAME`(指定网关名)和`BK_APIGW_STAGE`(指定环境)
   ```bash
    AIDEV_GATEWAY_NAME=aidev-test
    BK_APIGW_STAGE=stag
   ```

### Redis Streams MessageHandler

多进程部署可显式切换到 Redis Streams：

```bash
MESSAGE_HANDLER_TYPE=redis
MSG_REDIS_URL=redis://user:password@redis.example.com:6379/0
```

- 服务端最低版本为 Redis 6.2；版本、权限或必需数据命令校验失败时直接终止启动，不降级。
- 启动检查只使用 `HELLO` 和临时随机键上的普通数据命令，不调用管理类命令。
- 完成后的 Stream 默认保留 90 秒供其他活跃端回放，可用
  `MSG_REDIS_COMPLETED_STREAM_TTL_SECONDS` 调整；异常兜底 TTL 继续使用 `QUEUE_EXPIRE_SECONDS`。

## 构建
1. 生成`pip`包
    ```bash
    $ make build
    ```
2. 清理本地构建
    ```bash
    $ make clean
    ```
