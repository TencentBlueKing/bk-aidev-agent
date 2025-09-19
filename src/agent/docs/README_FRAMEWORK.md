# aidev-agent sdk使用指南

## 概览

**当前版本**：1.0.0b44

### 支持的能力：

- 通用 Agent：支持基于任意模型进行知识抽取，工具执行，利用添加的工具和知识完成特定任务。
- 通用 Tool/FunctionCallAgent：在上述基础上，对支持 FunctionCall 的模型提供最佳支持。支持最新的 OpenAI Multi Tool 规范，可并发执行
  Function Call。

## 使用入门

### 1. 安装依赖

系统版本：Linux,MacOS
Python版本：>=3.10;

```
$ pip install aidev-agent==1.0.0b44
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

#### 样例4：在蓝鲸主站中使用 SSM 客户端进行认证

**注意** 这个示例适用于在蓝鲸主站代码中集成 SSM 认证功能


```python
# -*- coding: utf-8 -*-
"""
在蓝鲸主站项目中使用 SSM 客户端
参考真实项目中的使用模式，保持简洁实用
"""

from dataclasses import dataclass
from typing import Optional
from aidev_agent.api.bk_ssm import SSMApi
from aidev_agent.api.ssm_client import SSMException

@dataclass
class UserLLMService:
    tenant_id: str
    space_id: str
    username: Optional[str] = None

    def get_access_token_for_external_api(self, request=None):
        """
        为调用外部API获取访问令牌
        """
        try:
            if request and self.username:
                # 用户态：使用当前用户身份
                ssm_client = SSMApi.get_user_client(request)
                return ssm_client.get_user_access_token()
            else:
                # 应用态：使用应用身份（适用于后台任务、定时任务等）
                ssm_client = SSMApi.get_client_client()
                return ssm_client.get_client_access_token()
        except SSMException as e:
            # 根据业务需要处理异常
            raise Exception(f"获取访问令牌失败: {e}")

    def call_external_service_with_auth(self, request=None):
        """
        调用需要认证的外部服务示例
        """
        access_token = self.get_access_token_for_external_api(request)

        # 使用 token 调用外部 API
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # 具体的API调用逻辑
        # response = requests.get(external_api_url, headers=headers)
        # return response.json()

        return {"token_obtained": True, "ready_for_api_call": True}

# 在 Django 视图中使用
def get_user_resources(request):
    """获取用户资源的API视图"""
    service = UserLLMService(
        tenant_id="your_tenant",
        space_id="your_space",
        username=request.user.username
    )

    try:
        # 获取需要认证的外部资源
        result = service.call_external_service_with_auth(request)
        return {"code": 0, "data": result}
    except Exception as e:
        return {"code": 500, "message": str(e)}

# 在后台任务中使用（无用户上下文）
def background_sync_task():
    """后台同步任务"""
    service = UserLLMService(
        tenant_id="your_tenant",
        space_id="your_space"
        # 注意：username=None，将使用应用态
    )

    try:
        # 后台任务使用应用态认证
        result = service.call_external_service_with_auth()
        return result
    except Exception as e:
        print(f"后台任务执行失败: {e}")
```

**最简化的使用方式：**

```python
from aidev_agent.api.bk_ssm import SSMApi

# 方式1：在有Django request的地方
def api_view(request):
    client = SSMApi.get_user_client(request)
    token = client.get_user_access_token()
    # 使用 token 调用外部API

# 方式2：在后台任务或定时任务中
def background_task():
    client = SSMApi.get_client_client()
    token = client.get_client_access_token()
    # 使用 token 调用外部API

# 方式3：智能模式
def smart_api_view(request):
    client = SSMApi.get_client_by_request(request)
    # 自动根据request判断使用用户态还是应用态
    if hasattr(request, 'user') and request.user.is_authenticated:
        token = client.get_user_access_token()
    else:
        token = client.get_client_access_token()
```

**环境配置（.env 文件）：**

```bash
# SSM 相关配置（选择其一即可）
BK_SSM_ENDPOINT=https://your-ssm-endpoint.com

# 或者分环境配置
BK_SSM_SG_ENDPOINT=https://bkssm.sg.example.com    # 生产环境
BK_SSM_BKOP_ENDPOINT=https://bkssm.bkop.example.com # 测试环境

# 应用认证信息
BKPAAS_APP_ID=your_app_code
BKPAAS_APP_SECRET=your_app_secret
```

### 注意事项

#### SSM 客户端使用注意事项：

1. **环境配置**: 确保正确配置了 SSM 相关的环境变量
2. **网络连接**: SSM 服务只能直调，不能通过网关访问
3. **Token 缓存**: 客户端内置了 token 缓存机制，避免频繁请求
4. **错误处理**: 合理处理 SSMException 异常
5. **线程安全**: SSMClient 支持多线程并发访问
