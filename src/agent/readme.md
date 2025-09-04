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
    ```
4. 如需指定网关或指定环境,可以配置环境变量`AIDEV_GATEWAY_NAME`(指定网关名)和`BK_APIGW_STAGE`(指定环境)
   ```bash
    AIDEV_GATEWAY_NAME=aidev-test
    BK_APIGW_STAGE=stag
   ```

## 构建
1. 生成`pip`包
    ```bash
    $ make build
    ```
2. 清理本地构建
    ```bash
    $ make clean
    ```
