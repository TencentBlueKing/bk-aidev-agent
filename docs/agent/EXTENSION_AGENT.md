# 智能体定制开发指南

## 概述

本文档提供智能体工具扩展的完整开发指南。通过本文档，您可以：
1. **配置智能体基础参数**：设置模型、工具、角色提示词等
2. **扩展自定义工具**：为智能体添加自定义功能工具
3. **集成MCP服务**：接入标准化的外部工具服务

## 快速开始

### 项目结构

```
bk_plugin/
├── config.py                      # 【重要】智能体配置文件
├── extend/
│   ├── agent.py                   # 【重要】自定义工具扩展入口
│   └── config_manager.py          # 配置管理器（一般无需修改）
├── versions/
│   └── assistant_components.py    # 【重要】配置加载器
└── docs/
    └── EXTENSION_AGENT.md  # 本文档
```

## 一、智能体基础配置

### 1.1 配置文件

配置文件位于 `bk_plugin/config.py`，用于设置智能体的基础参数。您可以参考文件中的提示进行修改。

### 1.2 配置项详解

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `chat_model` | 主要对话模型 | `"hunyuan-turbo"`, `"deepseek-r1"` |
| `non_thinking_llm` | 快速响应模型（用于意图识别等场景） | `"hunyuan-lite"` |
| `tool_codes` | 平台注册工具的代码列表 | `["weather_query", "db_query"]` |
| `role_prompt` | 角色提示词，追加到系统默认prompt之后 | `"你是Python专家"` |

### 1.3 配置生效路径

配置通过以下链路生效：
1. 智能体在运行时将读取 `settings.DEFAULT_CONFIG_MANAGER` 获取配置管理实例
2. 插件默认使用 `bk_plugin.extend.config_manager.CustomAgentConfigManager` 进行配置管理
3. `CustomAgentConfigManager` 将读取 `bk_plugin.config.AGENT_CONFIG` 覆盖平台配置

## 二、自定义工具扩展

### 2.1 扩展流程

自定义工具扩展在 `bk_plugin/extend/agent.py` 中进行，通过重写 `get_agent_executor` 方法添加工具。

**核心步骤：**
1. 定义工具函数（使用 `@tool` 装饰器）
2. 在 `CommonQAAgentExtend.get_agent_executor` 中注册工具
3. 工具自动集成到智能体的调用链中

### 2.2 完整示例

编辑 `bk_plugin/extend/agent.py`：

```python
from langchain_core.tools import tool
from aidev_agent.core.extend.agent.qa import CommonQAAgent


# ============================================
# 步骤1: 定义工具函数
# ============================================

@tool
def weather_query_tool(city: str) -> str:
    """查询指定城市的天气信息。

    Args:
        city: 城市名称，如 "北京" 或 "上海"

    Returns:
        天气信息字符串
    """
    # TODO: 实现工具逻辑
    # 可以是本地计算、调用远程API、查询数据库等任何逻辑

    # 示例1: 本地模拟数据
    weather_data = {
        "北京": "晴天，气温25°C，湿度60%",
        "上海": "多云，气温28°C，湿度70%",
    }
    return weather_data.get(city, f"暂无{city}的天气信息")

    # 示例2: 调用远程API（实际使用时取消注释）
    # import requests
    # url = f"https://api.example.com/weather?city={city}"
    # response = requests.get(url)
    # return response.json()["weather_info"]

# ============================================
# 步骤2: 注册工具到智能体
# ============================================

class CommonQAAgentExtend(CommonQAAgent):
    """扩展的智能体类，集成自定义工具"""

    @classmethod
    def get_agent_executor(cls, *args, **kwargs):
        """获取智能体执行器，在这里添加自定义工具"""
        # 获取已有的工具列表
        extra_tools = kwargs.get("extra_tools", [])

        # 添加自定义工具
        extra_tools.extend([
            weather_query_tool,
            # 在此添加更多工具...
        ])

        # 更新工具列表
        kwargs["extra_tools"] = extra_tools

        # 调用父类方法创建执行器
        return CommonQAAgent.get_agent_executor(*args, **kwargs)
```

### 2.3 工具开发规范

**工具函数规范：**

1. **必须使用 `@tool` 装饰器**
2. **函数文档字符串（docstring）非常重要**：LLM会根据docstring判断何时调用工具
3. **参数类型标注**：使用Python类型提示
4. **返回值**：通常返回字符串，便于LLM理解

**示例：完整的工具定义**

```python
from typing import List
from langchain_core.tools import tool

@tool
def search_documents(query: str, limit: int = 5) -> str:
    """在文档库中搜索相关内容。

    当用户询问技术文档、操作手册、最佳实践等问题时使用此工具。

    Args:
        query: 搜索关键词，尽量精确
        limit: 返回结果数量，默认5条

    Returns:
        搜索到的文档内容摘要

    Examples:
        - query="Kubernetes部署", limit=3
        - query="Python异步编程"
    """
    # 实现搜索逻辑
    results = perform_search(query, limit)
    return format_results(results)
```
更多工具开发规范请参考 [langchain官方文档-自定义工具](https://python.langchain.com.cn/docs/modules/agents/tools/how_to/custom_tools)


### 2.4 测试工具

**步骤1：启动本地服务**

```bash
python bin/manage.py runserver local.xxx.com:8000
```

**步骤2：测试调用**

```bash
curl -X POST http://local.xxx.com:8000/bk_plugin/plugin_api/chat_completion/     -H "Content-Type: application/json"     -d '{
        "chat_history": [
            {"role": "user", "content": "北京天气怎么样？"}
        ],
        "execute_kwargs": {"stream": false}
    }'
```

**步骤3：验证工具调用**

检查响应中是否包含工具调用结果，确认工具是否被正确触发。

## 三、MCP服务集成

### 3.1 MCP服务概述

MCP (Model Context Protocol) 是一个标准化协议，用于连接AI应用程序与外部工具和数据源。通过MCP，您可以快速集成第三方服务而无需编写适配代码。
更多MCP内容请参考 [MCP文档](https://modelcontextprotocol.io/)。

### 3.2 配置MCP服务

在 `bk_plugin/extend/agent.py` 中配置MCP服务：

```python
from aidev_agent.core.extend.agent.qa import CommonQAAgent
from aidev_agent.packages.langchain.tools.base import make_mcp_tools


# MCP服务配置
MCP_SERVER_CONFIG = {
    # 智谱AI的Web搜索MCP服务
    "zhipu-web-search": {
        "url": "https://open.bigmodel.cn/api/mcp-broker/proxy/web-search/mcp?Authorization=your-api-key",
        "transport": "streamable_http",
    },

    # 蓝鲸平台MCP服务示例
    "bk-example": {
        "url": "https://bk-example.com/sse/",
        "transport": "sse",
        "credential_type": "blueapps",  # 使用蓝鲸应用认证
    }
}


class CommonQAAgentExtend(CommonQAAgent):
    """扩展的智能体类，集成MCP工具"""

    @classmethod
    def get_agent_executor(cls, *args, **kwargs):
        extra_tools = kwargs.get("extra_tools", [])

        # 添加MCP工具
        try:
            mcp_tools = make_mcp_tools(MCP_SERVER_CONFIG)
            extra_tools.extend(mcp_tools)
            print(f"成功加载MCP工具: {[tool.name for tool in mcp_tools]}")
        except Exception as e:
            print(f"加载MCP工具失败: {e}")

        kwargs["extra_tools"] = extra_tools
        return CommonQAAgent.get_agent_executor(*args, **kwargs)
```

### 3.3 MCP配置说明

| 配置项 | 说明 | 示例                          |
|--------|------|-----------------------------|
| `url` | MCP服务地址 | `"https://example.com/mcp"` |
| `transport` | 传输协议：`sse` 或 `streamable_http` | `"sse"`                     |
| `credential_type` | 认证类型：`blueapps`（蓝鲸应用）或其他 | `"blueapps"` 或不填          |


蓝鲸平台MCP服务示例：

```python
"bk-example": {
    "url": "https://your-bk-domain.com/mcp/sops/",
    "transport": "sse",
    "credential_type": "blueapps",
}
```

> **注意**：使用MCP服务需要先申请对应的访问权限和API密钥，详情可通过以下位置查看：蓝鲸开发者中心 > API 网关 > MCP市场。

## 四、完整开发流程

### 4.1 开发流程总览

```
1. 修改 bk_plugin/config.py 配置基础参数
   ↓
2. 在 bk_plugin/extend/agent.py 中添加自定义工具
   ↓
3. 本地启动服务测试
   ↓
4. 验证工具调用是否正常
   ↓
5. 部署到生产环境
```

### 4.2 完整示例：构建SRE助手

**步骤1：配置基础参数**

编辑 `bk_plugin/config.py`：

```python
AGENT_CONFIG = {
    "chat_model": "hunyuan-turbo",
    "tool_codes": ["k8s_query"],  # 平台K8s查询工具
    "role_prompt": "你是一位资深的SRE专家，擅长Kubernetes、监控告警和故障排查。",
}
```

**步骤2：添加自定义工具**

编辑 `bk_plugin/extend/agent.py`：

```python
from langchain_core.tools import tool
from aidev_agent.core.extend.agent.qa import CommonQAAgent
import requests


@tool
def query_pod_status(namespace: str, pod_name: str) -> str:
    """查询K8s Pod状态。

    Args:
        namespace: 命名空间
        pod_name: Pod名称

    Returns:
        Pod状态信息
    """
    # 调用K8s API查询
    result = k8s_api.get_pod_status(namespace, pod_name)
    return f"Pod {pod_name} 状态：{result['status']}"


@tool
def check_alert_history(service_name: str, hours: int = 24) -> str:
    """查询告警历史。

    Args:
        service_name: 服务名称
        hours: 查询最近多少小时，默认24小时

    Returns:
        告警历史记录
    """
    # 查询监控系统
    alerts = monitoring_api.get_alerts(service_name, hours)
    return f"最近{hours}小时有{len(alerts)}条告警"


class CommonQAAgentExtend(CommonQAAgent):
    @classmethod
    def get_agent_executor(cls, *args, **kwargs):
        extra_tools = kwargs.get("extra_tools", [])

        # 添加SRE工具
        extra_tools.extend([
            query_pod_status,
            check_alert_history,
        ])

        kwargs["extra_tools"] = extra_tools
        return CommonQAAgent.get_agent_executor(*args, **kwargs)
```

**步骤3：启动测试**

```bash
# 启动服务
python bin/manage.py runserver local.xxx.com:8000

# 测试调用
curl -X POST http://local.xxx.com:8000/bk_plugin/plugin_api/chat_completion/ \
    -H "Content-Type: application/json" \
    -d '{
        "chat_history": [
            {"role": "user", "content": "查询 default 命名空间下 nginx-pod 的状态"}
        ],
        "execute_kwargs": {"stream": false}
    }'
```

### 4.3 调试技巧

**1. 打印工具列表**

```python
class CommonQAAgentExtend(CommonQAAgent):
    @classmethod
    def get_agent_executor(cls, *args, **kwargs):
        extra_tools = kwargs.get("extra_tools", [])
        extra_tools.extend([your_tool])

        # 打印工具信息，便于调试
        print(f"已加载工具: {[tool.name for tool in extra_tools]}")

        kwargs["extra_tools"] = extra_tools
        return CommonQAAgent.get_agent_executor(*args, **kwargs)
```

**2. 工具异常处理**

```python
@tool
def safe_api_call(param: str) -> str:
    """工具描述"""
    try:
        result = api_call(param)
        return str(result)
    except Exception as e:
        # 返回错误信息给LLM，让它能够理解并处理
        return f"调用失败: {str(e)}"
```

## 五、常见问题

### 5.1 工具没有被调用？

**可能原因：**
1. 工具的docstring描述不够清晰，LLM无法理解何时使用
2. 用户问题与工具功能不匹配
3. 没有正确重写CommonQAAgentExtend类中的get_agent_executor函数，导致工具未能正确注册到 `extra_tools`

**解决方案：**
- 优化工具的docstring，增加详细的使用场景说明
- 在工具描述中添加具体的示例用法
- 检查 `CommonQAAgentExtend`类中`get_agent_executor` 方法的工具注册代码

### 5.2 MCP工具加载失败？

**可能原因：**
1. MCP服务地址不可达
2. API密钥配置错误
3. 认证权限不足

**解决方案：**
- 检查MCP服务URL是否正确
- 验证API密钥是否有效
- 确认是否已申请MCP服务的访问权限


## 六、参考资源

- [LangChain Tool Documentation](https://python.langchain.com/docs/modules/agents/tools/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
---

如有问题，请联系技术支持或参考项目README文档。