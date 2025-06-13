# BK AIDev 平台

## 开发指南

### 初始化
1. 确认 Python 版本（3.10.x）
    ```bash
    python --version
    Python 3.10.5
   ```
   
2. 安装 `poetry`：Poetry 应该安装一个独立的环境，避免与项目环境互相影响
   ```shell
   curl -sSL https://install.python-poetry.org | python3 - --version 1.8.5
   ```

3. 初始化项目环境（虚拟环境位于项目根目录 `.venv` 下），此步骤将始化本地`pre-commit`组件
    ```bash
    $ make init
    ```

4. 执行 `pre-commit` 验证
   ```shell
   $ pre-commit
   ```

### 依赖包管理
1. `AIDev` 通过 `Poetry` 管理项目依赖，蓝鲸插件依赖需要通过 `Group` 管理
   ```bash
   # 平台依赖
   poetry add {package_name}~=1.0.0
   # 开发环境依赖
   poetry add {package_name}~=1.0.0 -G dev
   ```

2. 可以通过以下命令导出依赖对应的 `requirements.txt`
   ```bash
   poetry export -f requirements.txt --output requirements.txt --without-hashes
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
