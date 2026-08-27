# AI 智能体插件

## 一、Quickstart

### 1.1 关联智能体空间

1. 如果您是从开发者中心创建的智能体，请参考[FAQ](https://github.com/TencentBlueKing/bk-aidev-agent/blob/develop/docs/agent/FAQ.md#%E2%9D%93%E9%97%AE%E9%A2%98%EF%BC%9A%E5%85%B3%E8%81%94%E6%99%BA%E8%83%BD%E4%BD%93)文档，将智能体关联到所属的项目空间
2. 关联智能体后请务必配置并发布智能体

### 1.2 本地开发环境配置

1. 初始化项目环境，推荐使用 `uv`（>=0.7.14）管理依赖，虚拟环境将创建在项目根目录 `.venv` 下

```bash
# 使用 uv 管理依赖
curl -LsSf https://astral.sh/uv/install.sh | sh
make init # 如果没有make命令则使用 uv sync
```

### 1.3 本地环境变量配置

1. 通过以下命令创建本地环境变量文件

```shell
cp ./support-files/env.template .env
```

2. 修改 本地环境变量文件`.env`中的应用密钥变量`BKPAAS_APP_SECRET`，可通过【[蓝鲸开发者中心]({{cookiecutter.bkpaas_url}}/developer-center/apps/{{cookiecutter.app_code}}/summary) > 应用配置 > 密钥信息】获取

**注意：support-files/env.template 是环境变量模板，会提交到代码仓库，请勿配置敏感信息**

模板默认设置 `BKAI_AGENT_ENABLE_METRICS=false`，本地运行时会强制关闭指标，即使平台下发的
`agent_info.otel_info.metrics` 为启用状态也不会上报；需要联调指标时再显式改为 `true`。

### 1.4 启动服务并测试

#### 1.4.1 UNIX 系统

在启动本地服务前，需要先将 `local.{{cookiecutter.bkpaas_bk_domain}}` 配置到本地的 `hosts` 文件中

然后，执行以下脚本启动本地服务，即可开始测试：

```shell
make dev
```

`make dev` 会安装模板依赖、加载 `.env`、初始化数据库和缓存表，并根据 `BKPAAS_BK_DOMAIN` 以 `local.<BKPAAS_BK_DOMAIN>:8000` 启动服务。也可以手动执行：

```shell
source .env
source .venv/bin/activate
python bin/manage.py migrate
python bin/manage.py createcachetable

# 启动服务
python bin/manage.py runserver local.{{cookiecutter.bkpaas_bk_domain}}:8000
```

#### 1.4.2 Windows 系统

用户启动环境为 Windows 时，推荐使用`Git-bash`执行以下脚本启动本地服务，即可开始测试：

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
cruft link https://github.com/TencentBlueKing/bk-aidev-agent.git --directory template/builtin --config-file=./support-files/cookiecutter.yaml --no-input
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

如果智能体绑定的模型是支持图生文的模型,还可以以下面方式传图片

```
{
  "input": "用户内容",
  "chat_history": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "描述一下这张图片的内容"},
        {"type": "image_url", "image_url": { "url": "https://example.jpg" }},
      ]
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

- `access_token` 可通过【[蓝鲸开发者中心]({{cookiecutter.bkpaas_url}}/developer-center/apps/{{cookiecutter.app_code}}/summary) > 云 API 权限> 创建新令牌】获取

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

流式响应基于 [Agent User Interaction Protocol (AG-UI)](https://docs.ag-ui.com/concepts/events)，采用事件流架构，通过标准 SSE（Server-Sent Events）推送：每行形如 `data: <JSON>`，其中 JSON 为单条事件对象。

**基础约定**：所有事件均包含 `type` 字段（事件类型标识）；可选包含 `timestamp`、`rawEvent`（原始/转换前数据）等。

#### 事件分类概览

| 分类         | 说明                         |
| ------------ | ---------------------------- |
| 生命周期事件 | 一次 run 的开始、步骤与结束   |
| 文本消息事件 | 助手回复的流式内容           |
| 推理事件     | 推理/思考过程（含已废弃命名） |
| 状态事件     | 状态快照等                   |
| 特殊事件     | 自定义、透传外部系统事件     |

#### 生命周期事件（Lifecycle）

- **RUN_STARTED**：一次 agent run 开始
  - `threadId`：会话线程 ID
  - `runId`：本次 run ID
  - 可选：`parentRunId`、`input`
- **STEP_STARTED** / **STEP_FINISHED**：步骤开始/结束（可选，可多次）
  - `stepName`：步骤名（如 `"model"`）
- **RUN_FINISHED**：run 正常结束
  - `threadId`、`runId`；可选 `result`
- **RUN_ERROR**：run 异常结束
  - `message`；可选 `code`

#### 文本消息事件（Text Message）

流式回复采用「Start → Content(×N) → End」模式，由 `messageId` 关联同一消息：

- **TEXT_MESSAGE_START**：消息开始
  - `messageId`、`role`（如 `"assistant"`）；可选 `rawEvent`
- **TEXT_MESSAGE_CONTENT**：内容片段
  - `messageId`、`delta`（本段文本）；可选 `rawEvent`
- **TEXT_MESSAGE_END**：消息结束
  - `messageId`；可选 `rawEvent`

前端应按顺序拼接同一 `messageId` 的 `delta` 得到完整回复。

#### 推理事件（Reasoning / Thinking）

推理类模型（如带思考链的模型）会流式输出思考过程。协议推荐使用 **REASONING_*** 系列；当前实现中仍可能下发 **THINKING_***（已标记为废弃，后续将迁移到 REASONING_*）：

- **THINKING_START** / **THINKING_END**：推理段开始/结束（THINKING_END 可带 `duration`）
- **THINKING_TEXT_MESSAGE_START** / **THINKING_TEXT_MESSAGE_CONTENT** / **THINKING_TEXT_MESSAGE_END**：推理内容流式片段，`delta` 为思考文本

#### 工具调用事件（Tool Call）

当模型决定调用工具（如查询天气）时，会按「Start → Args(×N) → End → Result」顺序下发事件，由 `toolCallId` 关联同一次调用：

- **TOOL_CALL_START**：工具调用开始
  - `toolCallId`：本次工具调用 ID（如 `"functions.get_weather:0"`）
  - `toolCallName`：工具名（如 `"get_weather"`）
  - 可选：`parentMessageId`、`rawEvent`、`description`、`mcpName`
- **TOOL_CALL_ARGS**：工具参数流式片段（可多条）
  - `toolCallId`：与 TOOL_CALL_START 一致
  - `delta`：参数 JSON 的片段（需按顺序拼接成完整 JSON）
- **TOOL_CALL_END**：工具参数发送结束，即将执行工具
  - `toolCallId`；可选 `rawEvent`
- **TOOL_CALL_RESULT**：工具执行完毕后的返回
  - `messageId`：所属消息 ID
  - `toolCallId`：对应 TOOL_CALL_START 的 ID
  - `content`：工具返回内容（成功时为结果文本，失败时多为错误信息）
  - `role`：通常为 `"tool"`
  - 可选：`duration`（执行耗时）、`error`（是否为错误结果，如 `true`）

前端可按 `toolCallId` 拼接 TOOL_CALL_ARGS 的 `delta` 得到完整入参，并用 TOOL_CALL_RESULT 的 `content` 展示工具结果或错误。

#### 状态与特殊事件

- **STATE_SNAPSHOT**：完整状态快照
  - `snapshot`：当前状态（如 `messages` 等）
- **CUSTOM**：应用自定义事件
  - `name`：事件名（如 `"temp_message"`）
  - `value`：载荷
- **RAW**：透传外部/底层事件（如 LangChain/LangGraph 回调）
  - `event`：原始事件对象；可选 `source`

#### 示例（SSE 行内容）

```json
{"type":"RUN_STARTED","threadId":"xxx","runId":"31388"}
```

```json
{"type":"STEP_STARTED","stepName":"model"}
```

```json
{"type":"THINKING_START"}
```

```json
{"type":"THINKING_TEXT_MESSAGE_CONTENT","delta":"这是AI的思考内容 chunk"}
```

```json
{"type":"TEXT_MESSAGE_START","messageId":"lc_run--xxx","role":"assistant"}
```

```json
{"type":"TEXT_MESSAGE_CONTENT","messageId":"lc_run--xxx","delta":" 这戏AI的正文内容 chunk"}
```

```json
{"type":"TEXT_MESSAGE_END","messageId":"lc_run--xxx"}
```

```json
{"type":"TOOL_CALL_START","toolCallId":"functions.get_weather:0","toolCallName":"get_weather","parentMessageId":"lc_run--xxx"}
```

```json
{"type":"TOOL_CALL_ARGS","toolCallId":"functions.get_weather:0","delta":"{\""}
```

```json
{"type":"TOOL_CALL_ARGS","toolCallId":"functions.get_weather:0","delta":"北京"}
```

```json
{"type":"TOOL_CALL_END","toolCallId":"functions.get_weather:0"}
```

```json
{"type":"TOOL_CALL_RESULT","messageId":"xxx","toolCallId":"functions.get_weather:0","content":"获取天气失败: 北京","role":"tool","duration":3.0,"error":true}
```

```json
{"type":"STEP_FINISHED","stepName":"model"}
```

```json
{"type":"RUN_FINISHED","threadId":"xxx","runId":"019d053a-188b-75a0-9854-f4d04999f952"}
```

```json
{"type":"CUSTOM","name":"temp_message","value":{"message":"一些自定义的事件","status":"error"}}
```

完整事件类型与字段以 [AG-UI Events](https://docs.ag-ui.com/concepts/events) 为准；工具调用（Tool Call）、Activity 等事件形态也在该协议中定义，本服务在启用相应能力时会按同一规范下发。



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

## 五、升级与迁移

### 5.1 历史会话升级

如果您的智能体在升级到 AG-UI 协议之前已有历史会话数据，可通过以下命令将旧版会话升级为 AG-UI v2 协议格式：

```bash
# 使用默认批次大小（500）
python bin/manage.py upgrade_sessions

# 指定每批次处理数量（范围 1-5000）
python bin/manage.py upgrade_sessions --batch-size=1000
```

**说明：**

- 该命令会向 AIDev 平台提交一个异步升级任务
- 升级任务将在后台执行，不会阻塞当前操作
- 升级进度和结果请在 AIDev 平台查看
- 如果智能体没有旧版会话数据，无需执行此命令
