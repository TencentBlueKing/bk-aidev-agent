# SSM客户端使用文档

## 概述

SSM (Security Service Manager) 客户端提供了简洁的外部版本 access_token 获取、刷新和校验功能。支持用户态和应用态两种鉴权模式，具备缓存和自动刷新机制。

## 主要特性

- **双模态支持**: 用户态鉴权（使用bk_token）和应用态鉴权（client_credentials）
- **智能缓存**: 自动缓存token并管理过期时间
- **自动刷新**: token即将过期时自动刷新，无需手动处理
- **线程安全**: 支持多线程并发访问
- **多环境**: 支持SG、BKOP等不同环境

## 快速开始

### 1. 基本使用

```python
from aidev_agent.api.ssm_client import SSMClient

# 创建SSM客户端
client = SSMClient()
```

### 2. 获取应用态Token

```python
# 获取应用态access_token
access_token = client.get_client_access_token()
print(f"应用态Token: {access_token}")
```

### 3. 获取用户态Token

```python
# 获取用户态access_token
username = "your_username"
bk_token = "user_login_bk_token"
access_token = client.get_user_access_token(username, bk_token)
print(f"用户态Token: {access_token}")
```

## 详细使用

### SSMClient 直接使用

```python
from aidev_agent.api.ssm_client import SSMClient

# 使用默认配置创建客户端
client = SSMClient()

# 或自定义配置
client = SSMClient(
    base_url="https://your-ssm-endpoint.com",
    app_code="your_app_code",
    app_secret="your_app_secret",
    timeout=30
)

# 应用态鉴权 - 获取应用级别的token
client_token = client.get_client_access_token()

# 用户态鉴权 - 获取用户级别的token
user_token = client.get_user_access_token("username", "bk_token")

# 验证token有效性
verify_result = client.verify_access_token(client_token)
print(f"Token验证结果: {verify_result}")
```

### 使用API工厂类

```python
from aidev_agent.api.bk_ssm import SSMApi

# 获取应用态客户端
client = SSMApi.get_client_client()
access_token = client.get_client_access_token()

# 获取用户态客户端
client = SSMApi.get_user_client("username", "bk_token")
access_token = client.get_user_access_token("username", "bk_token")

# 在Django视图中使用
def api_view(request):
    client = SSMApi.get_client_by_request(request)
    access_token = client.get_client_access_token()
    # 使用token调用其他API
```

## 缓存管理

SSM客户端具备缓存机制：

```python
# 查看缓存状态
cache_info = client.get_cache_info()
print(f"当前缓存: {cache_info}")

# 清理特定用户的缓存
client.clear_cache("username")

# 清理所有缓存
client.clear_cache()
```

## 配置说明

### 环境变量

SSM客户端支持以下环境变量配置：

```bash
# SSM服务地址（不同环境）
BK_SSM_ENDPOINT=https://your-ssm.com          # 通用endpoint
BK_SSM_SG_ENDPOINT=https://sg-ssm.com         # SG环境
BK_SSM_BKOP_ENDPOINT=https://bkop-ssm.com     # BKOP环境

# 应用凭证
BK_AIDEV_AGENT_APP_CODE=your_app_code
BK_AIDEV_AGENT_APP_SECRET=your_app_secret
```

### 自动环境选择

客户端会根据运行环境自动选择合适的SSM endpoint：

- **PRODUCT模式**: 使用 `BK_SSM_SG_ENDPOINT`
- **其他模式**: 使用 `BK_SSM_BKOP_ENDPOINT`
- **手动指定**: 使用 `BK_SSM_ENDPOINT`

## Token管理

### Token生命周期

1. **创建**: 首次调用时创建新token
2. **缓存**: token自动缓存在内存中
3. **检查**: 每次使用前检查是否过期（提前5分钟）
4. **刷新**: 过期时自动刷新token
5. **失败处理**: 刷新失败时重新创建

### Token过期处理

```python
# Token会自动处理过期，无需手动干预
token1 = client.get_client_access_token()  # 创建新token
token2 = client.get_client_access_token()  # 返回缓存的token

# 5分钟后（假设token快过期）
token3 = client.get_client_access_token()  # 自动刷新token
```

## 错误处理

```python
from aidev_agent.api.ssm_client import SSMException

try:
    client = SSMClient()
    access_token = client.get_client_access_token()
except SSMException as e:
    print(f"SSM错误: {e}")
except Exception as e:
    print(f"其他错误: {e}")
```

## 最佳实践

### 1. 复用客户端实例

```python
# 推荐：创建一个客户端实例并复用
client = SSMClient()

def get_data():
    token = client.get_client_access_token()
    # 使用token调用API

def update_data():
    token = client.get_client_access_token()  # 复用缓存的token
    # 使用token更新数据
```

### 2. 选择合适的鉴权模式

```python
# 应用态：用于应用内部调用，不需要用户上下文
client_token = client.get_client_access_token()

# 用户态：需要用户身份验证的操作
user_token = client.get_user_access_token(username, bk_token)
```

### 3. 在Web应用中使用

```python
# Django示例
from django.http import JsonResponse
from aidev_agent.api.bk_ssm import SSMApi

def protected_api(request):
    try:
        # 根据需要选择鉴权方式
        client = SSMApi.get_client_by_request(request)

        # 对于需要用户身份的操作
        if request.user.is_authenticated:
            token = client.get_user_access_token(
                request.user.username,
                request.COOKIES.get('bk_token')
            )
        else:
            # 应用态操作
            token = client.get_client_access_token()

        # 使用token调用其他服务
        return JsonResponse({"token": token})

    except SSMException as e:
        return JsonResponse({"error": str(e)}, status=500)
```

## 测试支持

在测试环境中，可以通过mock来避免真实的网络请求：

```python
import responses
from aidev_agent.api.ssm_client import SSMClient

@responses.activate
def test_ssm_client():
    # Mock API响应
    responses.add(
        responses.POST,
        "https://test-ssm.com/api/v1/auth/access-tokens",
        json={"code": 0, "data": {"access_token": "test_token"}},
        status=200
    )

    client = SSMClient(
        base_url="https://test-ssm.com",
        http_client="requests"  # 确保使用requests以便mock
    )

    token = client.get_client_access_token()
    assert token == "test_token"
```

## 故障排查

### 常见问题

1. **SSL证书错误**: 检查网络环境和证书配置
2. **认证失败**: 验证app_code和app_secret是否正确
3. **网络超时**: 调整timeout参数或检查网络连接
4. **Token过期**: 客户端会自动处理，如频繁出现检查系统时间

### 调试信息

```python
import logging

# 启用调试日志
logging.basicConfig(level=logging.DEBUG)

client = SSMClient()
# 会看到详细的请求和缓存日志
```

## API参考

### SSMClient

主要方法：

- `get_client_access_token()`: 获取应用态token
- `get_user_access_token(username, bk_token)`: 获取用户态token
- `verify_access_token(token)`: 验证token有效性
- `clear_cache(username=None)`: 清理缓存
- `get_cache_info()`: 获取缓存信息

### SSMApi

工厂方法：

- `get_client_client()`: 获取应用态客户端
- `get_user_client(username, bk_token)`: 获取用户态客户端
- `get_client_by_request(request)`: 从request获取客户端

通过这个设计，你只需要关注两种核心使用场景：**用户态鉴权**和**应用态鉴权**，无需处理复杂的兼容模式和自定义环境配置。
