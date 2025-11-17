# AI 智能体插件

## 一、Quickstart
### 1.1 关联智能体空间
1. 如果您是从开发者中心创建的智能体，请参考[FAQ](https://github.com/TencentBlueKing/bk-aidev-agent/blob/develop/docs/agent/FAQ.md#%E2%9D%93%E9%97%AE%E9%A2%98%EF%BC%9A%E5%85%B3%E8%81%94%E6%99%BA%E8%83%BD%E4%BD%93)文档，将智能体关联到所属的项目空间
2. 关联智能体后请务必配置并发布智能体

### 1.2 本地开发环境配置

1. 初始化项目环境，通过 `uv`（>=0.7.14）或 `pip` 管理依赖，虚拟环境将创建在项目根目录 `.venv` 下
```bash
# 使用 uv 管理依赖
curl -LsSf https://astral.sh/uv/install.sh | sh
make init # 如果没有make命令则使用 uv sync

# 使用 pip 管理依赖
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1.3 本地环境变量配置

1. 通过以下命令创建本地环境变量文件
```shell
cp ./support-files/env.template .env
```

2. 修改 本地环境变量文件`.env`中的应用密钥变量`BKPAAS_APP_SECRET`，可通过【[蓝鲸开发者中心]({{cookiecutter.bkpaas_url}}/developer-center/apps/{{cookiecutter.app_code}}/summary) > 应用配置 > 密钥信息】获取

**注意：support-files/env.template 是环境变量模板，会提交到代码仓库，请勿配置敏感信息**

### 1.4 启动服务并测试
#### 1.4.1 UNIX系统
在启动本地服务前，需要先将 `local.{{cookiecutter.bkpaas_bk_domain}}` 配置到本地的 `hosts` 文件中

然后，执行以下脚本启动本地服务，即可开始测试：

```shell
source .env
source .venv/bin/activate
python bin/manage.py migrate
python bin/manage.py createcachetable

# 启动服务
python bin/manage.py runserver local.{{cookiecutter.bkpaas_bk_domain}}:8000
```
#### 1.4.2 Windows系统
用户启动环境为Windows时，推荐使用`Git-bash`执行以下脚本启动本地服务，即可开始测试：
```shell
source .env
source .venv/Scripts/activate
python bin/manage.py migrate
python bin/manage.py createcachetable

# 启动服务
python bin/manage.py runserver local.{{cookiecutter.bkpaas_bk_domain}}:8000
```

本地打开 `local.{{cookiecutter.bkpaas_bk_domain}}:8000` 即可使用小鲸进行会话

## 二、开发指引 

### 2.1 目录结构

```
├── bin
│   ├── manage.py # django manage.py cli 入口
│   └── post_compile  # 默认蓝鲸插件的部署钩子脚本
├── bk_plugin
│   ├── apis
│   │   └── urls.py # API路由配置，用于生成蓝鲸插件的用户态接口
│   ├── extend # 用于扩展功能
│   │   ├── agent.py # 自定义智能体扩展
│   │   └── config_manager.py # 配置管理器扩展
│   ├── forms # 蓝鲸插件在标准运维等场景使用的前端配置
│   ├── openapi/  # 用于生成蓝鲸插件的应用态接口
│   ├── patch # 对默认蓝鲸插件配置的补丁，主要扩展了路由
│   │   ├── plugin.py # 插件补丁
│   │   └── urls.py # 路由补丁
│   ├── versions
│   │   └── assistant.py # 蓝鲸插件invoke接口入口
│   ├── config.py # 智能体配置相关
│   ├── meta.py # 蓝鲸插件的meta配置
│   └── settings.py # Django设置
├── support-files
│   ├── cookiecutter.yaml  # 模板配置
│   └── env.template # 环境变量模板，此文件会上传到代码仓库，请勿添加应用密钥等敏感信息
├── .gitignore  # git 代码 ignore 配置
├── app_desc.yml # 蓝鲸插件 app_desc 运行配置
├── Makefile  # 开发环境构建工具
├── pyproject.toml  # python uv 依赖文件
├── README.md # 指引文档
├── requirements.txt # Python依赖包配置
├── runtime.txt # Python运行时版本配置
└── uv.lock # uv 依赖锁文件
```

### 2.2 代码提交
1. 如果智能体尚未提交到代码仓库，可通过以下操作提交
```shell
cd {{cookiecutter.project_name}}
git init
git add .
git commit -m "init repo"
git remote add origin replace_your_git_url
git push -u origin main
```

2. 安装 `GIT` pre-commit 检测工具
```shell
make init-pre-commit
```

3. 通过 `make lint` 可对智能体所有代码进行检测
```shell
make lint
```

### 2.3 依赖包管理

1. 智能体插件默认通过 `uv` 管理项目依赖，不同的模块需要通过 `Group` 管理
   ```shell
   # 平台依赖
   uv add {package_name}~=1.0.0
   # 开发环境依赖
   uv add {package_name}~=1.0.0 --dev
   ```
2. 可以通过以下命令导出 `requirements.txt`
   ```shell
   make requirements.txt
   ```

### 2.4 智能体模板关联：通过以下步骤可关联并同步 `AIDev` 平台最新的智能体模板

智能体模板可通过 `cruft` 管理并同步平台模板变更，可参考以下步骤实现模板同步：

1. 安装 `cruft`

```shell
uv add cruft --dev
```

2. 关联智能体模板
```shell
cd {{cookiecutter.project_name}}
cruft link https://github.com/TencentBlueKing/bk-aidev-agent.git --directory template --config-file=./support-files/cookiecutter.yaml --no-input
```

3. 提交 `cruft.json` 到代码仓库，请按实际代码分支处理
```shell
git add .
git commit -m "minor: add .cruft.json"
git push -u origin main
```

4. 验证模板是否已关联
```shell
cruft check
```

5. 模板更新检测与应用
```shell
cruft check

cruft update
 - v：查看差异
 - y: 更新模板
 - n: 取消操作
 - s: 跳过此次合并
```

6. 开发中遇到问题？请点击[常见问题](https://github.com/TencentBlueKing/bk-aidev-agent/tree/develop/docs/agent/FAQ.md)


## 三、API 调用

### 3.1 接口协议
```
{
  "input": "用户内容",
  "chat_history": [
    {
      "role": "user",
      "content": "用户内容"
    },
    {
      "role": "assistant",
      "content": "AI内容"
    }
  ],
  "execute_kwargs": {
    "stream": true
  }
}
```
1. input: 用户对话内容
2. chat_history：会话历史
3. execute_kwargs
 - stream：是否流式输出

### 3.2 应用态调用
1. 应用态接口必须通过 header 头（`X-BKAIDEV-USER`）传递用户信息

2. 本地调试
```shell
curl -X POST http://local.{{cookiecutter.bkpaas_bk_domain}}:8000/bk_plugin/openapi/agent/chat_completion/ \
    -H "Content-Type: application/json"   \
    -H "X-BKAIDEV-USER: username" \
    -d '{"chat_history":[{"role":"user","content":"hi"}], "execute_kwargs": {"stream": true}}'
```

3`APIGW` 调用：此方式需要在 `APIGW` 对请求的 `bk_app_code` 进行授权
```shell
curl -X POST {{ cookiecutter.apigw_manager_url_tmpl.format(api_name="bp-" + cookiecutter.app_code) }}/prod/bk_plugin/openapi/agent/chat_completion/  \
    -H "Content-Type: application/json"   \
    -H "X-Bkapi-Authorization: {\"bk_app_code\": \"{{cookiecutter.app_code}}\", \"bk_app_secret\": \"\"}" \
    -H "X-BKAIDEV-USER: username" \
    -d '{"chat_history":[{"role":"user","content":"hi"}], "execute_kwargs": {"stream": true}}'
```


### 3.3 用户态调用
1. 本地调试
```shell
curl -X POST http://local.{{cookiecutter.bkpaas_bk_domain}}:8000/bk_plugin/plugin_api/chat_completion/ \
    -H "Content-Type: application/json"   \
    -d '{"chat_history":[{"role":"user","content":"hi"}], "execute_kwargs": {"stream": true}}'
```

2. `APIGW` 调用：此方式需要在 `APIGW` 对请求的 `bk_app_code` 进行授权
 - `access_token` 可通过【[蓝鲸开发者中心]({{cookiecutter.bkpaas_url}}/developer-center/apps/{{cookiecutter.app_code}}/summary) >  云 API 权限> 创建新令牌】获取

```shell
curl -X POST {{ cookiecutter.apigw_manager_url_tmpl.format(api_name="bp-" + cookiecutter.app_code) }}/prod/bk_plugin/plugin_api/chat_completion/  \
    -H "Content-Type: application/json"   \
    -H "X-Bkapi-Authorization: {\"access_token\": \"\"}" \
    -d '{"chat_history":[{"role":"user","content":"hi"}], "execute_kwargs": {"stream": true}}'
```

### 3.4 蓝鲸插件调用
1. 在蓝鲸插件调用场景下，将按蓝鲸插件协议标准调用，此方式不支持流式输出
2. 本地调试
```shell
curl -X POST http://127.0.0.1:8000/bk_plugin/invoke/1.0.0assistant \
    -H "Content-Type: application/json"   \
    -d '{
        "inputs": {
            "command": "",
            "input": "SRE 是什么?",
            "chat_history": [
                {
                    "role": "system",
                    "content": "你是 SRE 专家"
                },
                {
                    "role": "assistant",
                    "content": "作为SRE（Site Reliability Engineering，站点可靠性工程）专家，我的核心职责是确保系统的可靠性、可扩展性和高效运维"
                }
            ]
        },
        "context": {
            "executor": "user"
        }
    }'
```

3. `APIGW` 调用：此方式需要在 `APIGW` 对请求的 `bk_app_code` 进行授权
```shell
curl -X POST {{ cookiecutter.apigw_manager_url_tmpl.format(api_name="bp-" + cookiecutter.app_code) }}/prod/invoke/1.0.0assistant/ \
    -H "Content-Type: application/json"   \
    -H "X-Bkapi-Authorization: {\"bk_app_code\": \"{{cookiecutter.app_code}}\", \"bk_app_secret\": \"\"}" \
    -d '{
        "inputs": {
            "command": "",
            "input": "SRE 是什么?",
            "chat_history": [
                {
                    "role": "system",
                    "content": "你是 SRE 专家"
                },
                {
                    "role": "assistant",
                    "content": "作为SRE（Site Reliability Engineering，站点可靠性工程）专家，我的核心职责是确保系统的可靠性、可扩展性和高效运维"
                }
            ]
        },
        "context": {
            "executor": "user"
        }
    }'
```

### 3.5 流式响应协议

1. 请求输出格式：流式响应遵循标准的SSE响应规范。响应的data内容为JSON字符串，具体协议如下：
  - event支持5种类型：text, think, reference_doc, done, error
  - text类型event，表示单个流式输出
    - 附带字段
      - content: 单个流式响应内容
  - think类型event，推理类LLM（如deepseek-r1）独有的内置think过程
    - 附带字段
      - content: 单个流式响应内容
  - reference_doc类型event，表示执行了知识库查询并检索到了可能相关的文档
    - 附带字段:
      - documents
  - done类型event，表示流式输出结束
    - 附带字段:
      - content: 最终完整输出（默认为前序所有流式内容集合，或自定义最终输出）
      - cover: 是否用最终输出覆盖前序已展示流式输出
  - error类型event，表示遇到异常，同时流式输出结束
    - 附带字段:
      - message
      - code
2. 可以在agent内部处理逻辑中使用 `langchain_core.callbacks.manager.dispatch_custom_event` 函数，从算法逻辑中分发自定义事件并在 `bk_plugin/apis/assistant.py` 中转换为上述标准流式事件

- 示例:

```json
{
  "event": "text",
  "content": "这是AI助手"
}
```

```json
{
  "event": "text",
  "content": "的回答。"
}
```

```json
{
  "event": "think",
  "content": "这是AI助手的思考过程。"
}
```

```json
{
  "event": "done",
  "content": "这是AI助手的完整回答。",
  "cover": false
}
```

```json
{
  "event": "reference_doc",
  "documents": [{ "metadata": {} }]
}
```

```json
{
  "event": "error",
  "code": 400,
  "message": "发生错误"
}
```

## 四、智能体配置及定制开发
### 4.1 智能体自定义应用
1. 如果智能体需要自定义其它业务逻辑，建议在`apps`目录下创建`django application`
2. 应用创建后可以通过`bk_plugin/settings.py` 加载，应用涉及的配置建议直接在应用下的`settings.py`定义
```python
load_settings("apps.demo.settings")  # 自定义 demo 应用
```

### 4.2 智能体配置

智能体会自动从平台获取配置作为默认配置。同时，如果在 `bk_plugin/config.py` 的 `AGENT_CONFIG` 中定义配置，将覆盖平台获取的配置。
例如，需要将默认模型修改为 `deepseek-r1`：

```python
AGENT_CONFIG = {
  "chat_model": "deepseek-r1"
}
```

**注意：一般情况下，推荐直接在平台修改智能体配置**

### 4.3 智能体定制开发指南

当通用智能体无法满足业务场景时，可参考以下文档扩展智能体功能：
[智能体定制开发指南](https://github.com/TencentBlueKing/bk-aidev-agent/tree/develop/docs/agent/EXTENSION_AGENT.md)
