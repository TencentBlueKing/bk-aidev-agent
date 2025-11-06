# AI 智能体插件

## 一、Quickstart

### 1.1 本地环境配置

1. 初始化 `python` 虚拟环境，可通过 `uv`（推荐，版本>=0.7.14）或 `pip` 创建虚拟环境并管理依赖
```bash
# 安装 uv（已安装可跳过）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 基于 UNIX 系统可直接使用 `make` 命令进行初始化
make

# 使用 uv 方式
uv sync --inexact

# 使用 pip 方式
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. 运行时配置可通过以下步骤设置环境变量
```bash
cp ./support-files/env.template .env
```
 - `.env` 主要包含蓝鲸开发者中心内置环境变量，可在开发者中心查看对应变量
 - `AIDEV_SPACE_ID` 是应用在平台的空间ID，可通过【bkaidev主站 > 选择空间 > 智能体 > 选中当前智能体 > 去配置】获取，当前页面URL中 x-space-id= 后面的字符串即为此值
 - `BKPAAS_APP_SECRET` 是应用密钥信息，可通过【蓝鲸开发者中心 > 应用配置 > 密钥信息】获取
 - 其它环境变量会在平台初始化时自动生成，如有需要，可通过【蓝鲸开发者中心 > 模块配置 > 环境变量】获取

**注意：support-files/env.template 是环境变量模板，会提交到代码仓库，请勿配置敏感信息**

### 1.2 启动服务并测试

在执行本地服务前，需要先将 `local.{{cookiecutter.bk_paas_domain}}` 配置到本地的 `hosts` 文件中

然后，执行以下脚本启动本地服务，即可开始测试：

```bash
source .env
source .venv/bin/activate
python bin/manage.py migrate
python bin/manage.py createcachetable

# 绑定智能体到 AIDev 空间（如已操作可跳过此步骤）
python bin/manage.py agent_migrate
python bin/manage.py runserver local.{{cookiecutter.bk_paas_domain}}:8000
```

本地打开 `local.{{cookiecutter.bk_paas_domain}}:8000` 即可使用小鲸进行会话

## 二、开发指引

### 2.1 智能体配置

智能体会自动从平台获取配置作为默认配置。同时，如果在 `bk_plugin/config.py` 的 `AGENT_CONFIG` 中定义配置，将覆盖平台获取的配置。
例如，需要将默认模型修改为 `deepseek-r1`：

```python
AGENT_CONFIG = {
  "chat_model": "deepseek-r1"
}
```

**注意：一般情况下，推荐直接在平台修改智能体配置**

### 2.2 智能体定制开发指南

当通用智能体无法满足业务场景时，可参考以下文档扩展智能体功能：
[智能体定制开发指南](https://github.com/TencentBlueKing/bk-aidev-agent/tree/develop/docs/agent/EXTENSION_AGENT.md)


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
      "role": "assitant",
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
3. execute_kwargs.stream：是否流式输出

### 3.2 应用态调用
1. 本地调试
```bash
curl -X POST http://local.{{cookiecutter.bk_paas_domain}}:8000/bk_plugin/openapi/agent/chat_completion/ \
    -H "Content-Type: application/json"   \
    -d '{"chat_history":[{"role":"user","content":"hi"}], "execute_kwargs": {"stream": true}}'
```

2. `APIGW` 调用
```bash
curl -X POST {{ cookiecutter.apigw_manager_url_tmpl.format(api_name=cookiecutter.app_apigw_name) }}/bk_plugin/openapi/agent/chat_completion/  \
    -H "Content-Type: application/json"   \
    -H "X-Bkapi-Authorization": xxx   \
    -d '{"chat_history":[{"role":"user","content":"hi"}], "execute_kwargs": {"stream": true}}'
```


### 3.3 用户态调用
1. 本地调试
```bash
curl -X POST http://local.{{cookiecutter.bk_paas_domain}}:8000/bk_plugin/plugin_api/chat_completion/ \
    -H "Content-Type: application/json"   \
    -d '{"chat_history":[{"role":"user","content":"hi"}], "execute_kwargs": {"stream": true}}'
```

2. `APIGW` 调用
```bash
curl -X POST {{ cookiecutter.apigw_manager_url_tmpl.format(api_name=cookiecutter.app_apigw_name) }}/bk_plugin/plugin_api/chat_completion/  \
    -H "Content-Type: application/json"   \
    -H "X-Bkapi-Authorization": xxx   \
    -d '{"chat_history":[{"role":"user","content":"hi"}], "execute_kwargs": {"stream": true}}'
```

### 3.4 蓝鲸插件调用
1. 在蓝鲸插件调用场景下，将按蓝鲸插件协议标准调用，此方式不支持流式输出
2. 本地调试
```bash
curl -X POST http://127.0.0.1:8000/bk_plugin/invoke/1.0.0assistant \
    -H "Content-Type: application/json"   \
    -d '{
        "inputs": {
            "command": "",
            "input": "SRE 是什么?",
            "stream": true,
            "chat_history": [
                {
                    "role": "system",
                    "content": "你是 SRE 专家"
                },
                {
                    "role": "assistant",
                    "content": "作为SRE（Site Reliability Engineering，站点可靠性工程）专家，我的核心职责是确保系统的可靠性、可扩展性和高效运维"
                }
            ],
            "context": []
        },
        "context": {
            "executor": "user"
        }
    }'
```

3. `APIGW` 调用
```bash
curl -X POST{{ cookiecutter.apigw_manager_url_tmpl.format(api_name=cookiecutter.app_apigw_name) }}/invoke/1.0.0assistant \
    -H "Content-Type: application/json"   \
    -H "X-Bkapi-Authorization": xxx   \
    -d '{
        "inputs": {
            "command": "",
            "input": "SRE 是什么?",
            "stream": true,
            "chat_history": [
                {
                    "role": "system",
                    "content": "你是 SRE 专家"
                },
                {
                    "role": "assistant",
                    "content": "作为SRE（Site Reliability Engineering，站点可靠性工程）专家，我的核心职责是确保系统的可靠性、可扩展性和高效运维"
                }
            ],
            "context": []
        },
        "context": {
            "executor": "user"
        }
    }'
```

### 3.5 流式响应协议

1. 请求输入格式：流式响应遵循标准的SSE响应规范。响应的data内容为JSON字符串，具体协议如下：
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

## 四、项目结构

```
├── app_desc.yml # 蓝鲸插件 app_desc 运行配置
├── bin
│   ├── manage.py # django manage.py cli 入口
│   └── post_compile  # 默认蓝鲸插件的部署钩子脚本
├── bk_plugin
│   ├── apis
│   │   └── urls.py # API路由配置
│   ├── config.py # 智能体配置相关
│   ├── docs
│   │   └── EXTENSION_AGENT.md # 二次开发智能体文档
│   ├── extend # 用于扩展
│   │   ├── agent.py # 自定义智能体扩展
│   │   └── config_manager.py # 配置管理器扩展
│   ├── openapi/  # 用于生成蓝鲸插件的应用态接口
│   ├── meta.py # 蓝鲸插件的meta配置
│   ├── patch # patch了默认蓝鲸插件的配置,主要是扩展了路由
│   │   ├── plugin.py # 插件补丁
│   │   └── urls.py # 路由补丁
│   ├── settings.py # Django设置
│   └── versions
│       ├── assistant_components.py # 【重要】导入config.py的配置
│       └── assistant.py # 蓝鲸插件invoke接口入口
├── README.md # 指引文档
├── requirements.txt # Python依赖包配置
└── runtime.txt # Python运行时版本配置
```

### 五、智能体模板管理
智能体模板可通过`cruft`管理并同步平台模板变更，可参考以下实现同步模板内容

#### 5.1 模板初始化
1. 安装`cruft`

```bash
pip install cruft
```

2. 通过`cruft`创建智能体插件：适用于全新的智能体开发
```bash
cruft create https://github.com/TencentBlueKing/bk-aidev-agent.git --checkout develop --directory template
```

3. 添加远程仓库地址并完成推送：适用于代码未通过 `git` 管理的情况
```bash
cd {{cookiecutter.project_name}}
git init
git add .
git commit -m "init repo"
git remote add origin ${git_url}
git push -u origin main
```

4. 关联智能体模板：适于从AIDev或开发者中心创建的智能体，代码需要先提交到 git 仓库
```bash
cruft link https://github.com/TencentBlueKing/bk-aidev-agent.git --checkout develop --directory template --no-input
```

5. 验证模板是否已关联
```bash
cruft check --checkout develop 
```

#### 5.2 模板同步
检查或更新模板前需确保本地代码已提交到 GIT 仓库

1. 检查模板是否更新

```bash
cruft check --checkout develop 
```

2. 合并模板到本地项目

```bash
cruft update --checkout develop
```
