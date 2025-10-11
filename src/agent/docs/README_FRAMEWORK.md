# aidev-agent sdk使用指南

## 概览

**当前版本**：1.0.0b9

### 支持的能力：

- 通用 Agent：支持基于任意模型进行知识抽取，工具执行，利用添加的工具和知识完成特定任务。
- 通用 Tool/FunctionCallAgent：在上述基础上，对支持 FunctionCall 的模型提供最佳支持。支持最新的 OpenAI Multi Tool 规范，可并发执行
  Function Call。

## 使用入门

### 1. 安装依赖

系统版本：Linux,MacOS
Python版本：>=3.10;

```
$ pip install aidev-agent==1.0.0b9
```

### 2. 使用样例

#### 2.1 使用前配置

使用前需要配置的一些环境变量,可以将下面配置写到`.env`中,下面是一些示例

```
# (必选)以下环境变量可以向aidev的服务的管理员获取
LLM_GW_ENDPOINT=https://xxx.example.com/prod/openapi/aidev/gateway/llm/v1
# 个人拥有的蓝鲸app应用名
APP_ID=xxx
BKPAAS_APP_ID=xxx
# 个人拥有的蓝鲸app应用密钥
APP_TOKEN=yyy
BKPAAS_APP_SECRET=yyy

# (可选)如果需要访问aidev平台资源,如知识库/工具,需要配置下面的环境变量
# 当前可访问的蓝鲸网关的模板名,可以在蓝鲸开发者平台中获取
BK_API_URL_TMPL=http://{api_name}.xxx.com
```

另外,至少需要申请以下`bkaidev`网关的权限,以访问`LLM Gateway`,参考下图

![](./resources/pic01.png)

#### 样例1：调用 LLM Gateway 大模型服务

```python
from aidev_agent.core.extend.models.llm_gateway import ChatModel
model = ChatModel.get_setup_instance(model="hunyuan")
result = model.invoke("hi")
print(result)
```

#### 样例2：使用 CommonAgent 调用aidev平台上的工具

**注意** 使用前需要配置以下环境变量

```
# 当前可访问的蓝鲸网关的模板名,可以在蓝鲸开发者平台中获取,下面是示例
BK_API_URL_TMPL=http://{api_name}.xxx.com
```

另外,至少还需要申请下面的网关权限，才能完成样例

![](./resources/pic02.png)

代码示例如下:

```python
from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.core.extend.agent.qa import CommonQAAgent
from aidev_agent.core.extend.models.llm_gateway import ChatModel

model_name = "hunyuan"
chat_model = ChatModel.get_setup_instance(
    model=model_name,
    streaming=True,
)

# 获取客户端对象
client = BKAidevApi.get_client_by_username(username="")
# 设置工具,使用aidev平台上的工具的 code
tool_codes = ["weather-query"]
tools = [client.construct_tool(tool_code) for tool_code in tool_codes]

agent_e, cfg = CommonQAAgent.get_agent_executor(
    chat_model,
    chat_model,
    extra_tools=tools,
)

# 测试部分
test_case_inputs = {"input": "今天深圳天气如何?"}
for each in agent_e.agent.stream_standard_event(agent_e, cfg, test_case_inputs):
    print(each)
```


#### 样例3：使用 CommonAgent 调用aidev平台的知识库

**注意** 使用前需要配置以下环境变量

```
# 当前可访问的蓝鲸网关的模板名,可以在蓝鲸开发者平台中获取,下面是示例
BK_API_URL_TMPL=http://{api_name}.xxx.com
```

另外,至少还需要申请下面的网关权限，才能完成样例

![](./resources/pic03.png)

代码示例如下:

```python
from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.core.extend.agent.qa import CommonQAAgent
from aidev_agent.core.extend.models.llm_gateway import ChatModel

# 初始化模型和客户端
model_name = "hunyuan"
chat_model = ChatModel.get_setup_instance(
    model=model_name,
    streaming=True,
)
client = BKAidevApi.get_client_by_username(username="")
# 此处填入aidev平台上的知识库的 id
knowledge_bases = [client.api.appspace_retrieve_knowledgebase(path_params={"id": 1})["data"]]

agent_e, cfg = CommonQAAgent.get_agent_executor(
    chat_model,
    chat_model,
)

# 执行测试
test_case_inputs = {"input": "云桌面绿屏怎么办"}
results = []
for each in agent_e.agent.stream_standard_event(agent_e, cfg, test_case_inputs):
    if each == "data: [DONE]\n\n":
        break
    if each:
        chunk = json.loads(each[6:])
        results.append(chunk)

print(results)
```

# SSM 客户端使用指南

SSM客户端，用于获取、校验、刷新 access_token。

⚠️ **注意：SSM 只能直调，不能走网关！**

## 环境配置

```bash
# (必选) 应用认证信息
APP_CODE=your_app_code              # 或 BKPAAS_APP_ID 或 APP_ID
SECRET_KEY=your_app_secret          # 或 BKPAAS_APP_SECRET 或 APP_TOKEN

# (可选) SSM端点
BK_SSM_ENDPOINT=https://bkssm.service.consul  # （默认）

```

## 使用方法

### 基础调用

```python
from aidev_agent.api import SSMApi

# 使用默认配置
client = SSMApi.get_client()

# 或自定义认证信息
client = SSMApi.get_client(app_code="custom_code", app_secret="custom_secret")
```

### 获取应用态Token

```python
from aidev_agent.api import SSMApi

client = SSMApi.get_client()
response = client.create_access_token({
    "grant_type": "client_credentials",
    "id_provider": "client"
})

if response["code"] == 0:
    access_token = response["data"]["access_token"]
    print(f"应用态Token: {access_token}")
else:
    print(f"获取失败: {response['message']}")
```

### 获取用户态Token

```python
from aidev_agent.api import SSMApi

client = SSMApi.get_client()
response = client.create_access_token({
    "grant_type": "authorization_code",
    "id_provider": "bk_login",
    "bk_token": "user_bk_token_here"
})

if response["code"] == 0:
    access_token = response["data"]["access_token"]
    refresh_token = response["data"]["refresh_token"]
    print(f"用户态Token: {access_token}")
```

### 校验Token

```python
from aidev_agent.api import SSMApi

client = SSMApi.get_client()
response = client.verify_access_token({
    "access_token": "token_to_verify"
})

if response["code"] == 0:
    identity = response["data"]["identity"]
    print(f"Token有效，用户: {identity.get('username', 'N/A')}")
```

### 刷新Token

```python
from aidev_agent.api import SSMApi

client = SSMApi.get_client()
response = client.refresh_access_token({
    "refresh_token": "your_refresh_token"
})

if response["code"] == 0:
    new_access_token = response["data"]["access_token"]
    print(f"新Token: {new_access_token}")
```

## 完整示例

```python
from aidev_agent.api import SSMApi

def demo_ssm_workflow():
    # 获取客户端
    client = SSMApi.get_client()

    # 1. 获取应用态token
    app_response = client.create_access_token({
        "grant_type": "client_credentials",
        "id_provider": "client"
    })

    if app_response["code"] != 0:
        print(f"获取应用态token失败: {app_response['message']}")
        return

    access_token = app_response["data"]["access_token"]
    refresh_token = app_response["data"]["refresh_token"]
    print(f"应用态Token: {access_token}")

    # 2. 校验token
    verify_response = client.verify_access_token({
        "access_token": access_token
    })

    if verify_response["code"] == 0:
        print("Token校验成功")
        bk_app_code = verify_response["data"].get("bk_app_code")
        print(f"应用: {bk_app_code}")

    # 3. 刷新token
    refresh_response = client.refresh_access_token({
        "refresh_token": refresh_token
    })

    if refresh_response["code"] == 0:
        new_token = refresh_response["data"]["access_token"]
        print(f"刷新后的Token: {new_token}")

if __name__ == "__main__":
    demo_ssm_workflow()
```


