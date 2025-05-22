# Quickstart

## 1. 本地快速启动

### 1.1 配置环境

执行下面的脚本,创建虚拟环境&安装依赖

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
```

根据实际情况,更新`.env`文件末尾对应的`BKPAAS_APP_SECRET`.

### 1.2 启动服务并测试

执行下面脚本本地启动服务,即可开始测试

```bash
source .env
python bin/manage.py migrate
python bin/manage.py runserver 0.0.0.0:5000
```

本地打开`localhost:5000`即可使用小鲸进行会话

### 1.3 开发指引

#### 1.3.1 更新配置

更新当前目录的`agent/config.py`文件即可自定义所需的配置,例如需要修改默认的模型变为`deepseek-r1`.

```python
AGENT_CONFIG = {
  "chat_model": "deepseek-r1"
}
```

如果智能体是在平台创建的,可以打开`SYNC_CONFIG_FROM_AIDEV`配置,同步平台智能体配置的更新

```python
SYNC_CONFIG_FROM_AIDEV = True
```

### 1.4 api 调用

#### 1.4.1 标准运维插件调用

**请求输入格式**

- 整体格式：`{"inputs": {"input": "$你的需求", "chat_history": []},"context": {"executor": "someone"}}`
- `chat_history`：在此处传递除了当前输入外的聊天历史记录。格式：
  `[{"role": "user", "content": "用户内容"},{"role": "assitant", "content": "AI内容"}]`

智能体本地开发调用示例

```bash
curl -X POST http://127.0.0.1:8000/bk_plugin/invoke/1.0.0assistant \
    -H "Content-Type: application/json"   \
    -d '{
        "inputs": {
            "command": "chat",
            "input": "SRE 可观测性有哪些领域?",
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

智能体网关API调用示例

```bash
curl -X POST {{cookiecutter.app_apigw_host}}/invoke/1.0.0assistant \
    -H "Content-Type: application/json"   \
    -H "X-Bkapi-Authorization": xxx   \
    -d '{
        "inputs": {
            "command": "chat",
            "input": "SRE 可观测性有哪些领域?",
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


#### 1.4.2 流式调用

**请求输入格式**

- 整体格式：`{"inputs": {"input": "$你的需求", "chat_history": []},"context": {"executor": "someone"}}`
- `chat_history`：在此处传递除了当前输入外的聊天历史记录。格式：
  `[{"role": "user", "content": "用户内容"},{"role": "assitant", "content": "AI内容"}]`

智能体本地开发调用示例

```bash
curl -X POST http://127.0.0.1:8000/bk_plugin/plugin_api/chat_completion/ \
    -H "Content-Type: application/json"   \
    -d '{"chat_history":[{"role":"user","content":"hi"}], "execute_kwargs": {"stream": true}}'
```

智能体网关API调用示例

```bash
curl -X POST {{cookiecutter.app_apigw_host}}/bk_plugin/plugin_api/chat_completion/  \
    -H "Content-Type: application/json"   \
    -H "X-Bkapi-Authorization": xxx   \
    -d '{"inputs": {"chat_history": [{"role": "user", "content": "how are you?"}]}, "context": {"executor": "user"}}'
```

#### 1.4.3 非流式调用

智能体本地开发调用示例

```bash
curl -X POST http://127.0.0.1:8000/bk_plugin/plugin_api/chat_completion/ \
    -H "Content-Type: application/json"   \
    -d '{"chat_history":[{"role":"user","content":"hi"}], "execute_kwargs": {"stream": false}}'
```

智能体网关API调用示例

```bash
curl -X POST {{cookiecutter.app_apigw_host}}/bk_plugin/plugin_api/chat_completion/  \
    -H "Content-Type: application/json"   \
    -H "X-Bkapi-Authorization": xxx   \
    -d '{"inputs": {"chat_history": [{"role": "user", "content": "how are you?"}]}, "context": {"executor": "user"}}'
```


#### 1.4.4 流式响应协议

- 流式响应遵从标准的SSE响应规范。响应的data具体内容为JSON字符串，具体协议如下：
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


- 可以在agent内部处理逻辑中使用`langchain_core.callbacks.manager.dispatch_custom_event`函数，从算法逻辑中分发自定义事件并在`bk_plugin/apis/assistant.py`中转换为上述标准流式事件。


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
    "documents": [{"metadata": {}}]
}
```

```json
{
    "event": "error",
    "code": 400,
    "message": "发生错误"
}
```

### 1.5 项目结构

```
├── agent  # 用于二开的django app目录
│   ├── config.py # 自定义配置,可覆盖默认配置
│   ├── services
│   │   └── agent.py # agent 二开入口
│   └── views
│       └── builtin.py # 内置url入口,请勿修改
├── .env.template # 本地测试用环境变量
├── app_desc.yml  # 项目启动配置
├── bk_plugin  # 标准蓝鲸插件目录,请勿修改
│   ├── apis  # 蓝鲸插件api地址,以`/bk_plugin/plugin_api/`前缀暴露到api网关中
│   └── versions
│       ├── assistant.py # 蓝鲸插件入口,通过`invoke`方式调用
│       └── assistant_components.py # 智能体配置,由模板生成
```