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
MESSAGE_REDIS_URL=redis://user:password@redis.example.com:6379/0
```

- 服务端最低版本为 Redis 6.2；版本、权限或必需数据命令校验失败时直接终止启动，不降级。
- 启动检查只使用 `HELLO` 和临时随机键上的普通数据命令，不调用管理类命令。
- 完成后的 Stream 默认保留 90 秒供其他活跃端回放，可用
  `MESSAGE_REDIS_COMPLETED_STREAM_TTL_SECONDS` 调整；异常兜底 TTL 继续使用 `QUEUE_EXPIRE_SECONDS`。
- Producer 提交 EOD 后直接启用完成态 TTL，不再启动 100ms 轮询清理；活跃 Consumer 心跳会在回放期间
  原子续期 Stream，释放后由 Redis TTL 自动回收。
- 跨进程取消信号的空结果最多缓存 200ms，限制高频 chunk 产生的 Redis `GET`，同进程 Stop 会立即失效缓存。

### RabbitMQ Stream MessageHandler

RabbitMQ handler 默认继续使用 Classic Queue。配置原生 Stream 协议端口后，控制面仍使用 AMQP 0.9.1，
SSE 事件日志自动切换到 RabbitMQ Stream：

```bash
MESSAGE_HANDLER_TYPE=rabbitmq
RABBITMQ_HOST=rabbitmq.example.com
RABBITMQ_PORT=5672
RABBITMQ_STREAM_PORT=5552
```

- RabbitMQ 服务端需启用内置 `rabbitmq_stream` 插件，并向客户端正确发布 advertised host/port。
- `RABBITMQ_STREAM_PORT` 一旦配置即严格启用 Stream；协议端口、插件或认证不可用时启动失败，不降级到 Classic Queue。
- SSE 事件使用原生 offset 独立回放，多端消费不会 `get/nack` 历史消息；生产使用命名 publisher、批量发送和 broker confirm。
- Stream 数据按 `QUEUE_EXPIRE_SECONDS` 设置 `max-age`，正常结束仍由最后一个消费者或孤儿清理任务删除 Stream 与控制资源。

## 构建
1. 生成`pip`包
    ```bash
    $ make build
    ```
2. 清理本地构建
    ```bash
    $ make clean
    ```
