# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import contextlib
import json
import re
from hashlib import md5
from logging import getLogger
from typing import Any, Dict, List, Optional, Type

import requests
from langchain_core.prompts import jinja2_formatter
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langchain_core.tools.base import ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, Field, ValidationError, create_model, field_validator
from requests.exceptions import JSONDecodeError
from typing_extensions import Annotated

from aidev_agent.config import settings
from aidev_agent.enums import CredentialType
from aidev_agent.utils.loop import get_event_loop

from .enums import FieldType, FuncType
from .exceptions import ToolValidationError

try:
    from bkoauth import get_access_token_by_user
except ImportError:
    get_access_token_by_user = None


COMPLEXED_FIELD_TYPE = ["object", "array"]

_logger = getLogger(__name__)


class Rule(BaseModel):
    func: FuncType
    message: str
    value: str | int | float | bool


class Validator(BaseModel):
    enable: bool = Field(False)
    rules: list[Rule]


class MCPServerConfig(BaseModel):
    """MCP服务配置"""

    command: Optional[str] = None
    args: List[str] = []
    url: Optional[str] = None
    transport: Optional[str] = None
    headers: Optional[Dict[str, Any]] = None
    description: str = ""


class BkField(BaseModel):
    """用户输入字段"""

    name: str
    required: bool
    type: FieldType
    default: Any
    validates: Validator
    description: str

    def generate_field(self):
        if self.required and not self.default:
            return Field(..., description=self.description)
        else:
            _default = self.default
            if self.type in (FieldType.ARRAY, FieldType.OBJECT):
                _default = json.loads(self.default)
            return Field(_default, description=self.description)

    def get_python_type(self) -> Type[str | int | float | bool | list | dict]:
        if self.type == FieldType.STRING:
            return str
        elif self.type == FieldType.BOOLEAN:
            return bool
        elif self.type == FieldType.OBJECT:
            return dict
        elif self.type == FieldType.ARRAY:
            return list
        elif self.type == FieldType.INTEGER:
            return int
        else:
            # for number type , infer the default value
            return type(self.default) if self.default else float


class ToolExtra(BaseModel):
    query: dict | None = None
    header: dict | None = None
    body: dict | None = None
    path: dict | None = None


class Tool(BaseModel):
    """工具定义"""

    tool_id: int | None = None
    tool_code: str
    tool_name: str
    description: str
    method: str
    property: dict
    url: str
    extra: dict | None = None


class ApiWrapper:
    """工具API wrapper"""

    # 如果同个请求调用过多,则返回此prompt
    CALL_TOO_MUCH_PROMPT: str = """Same request call too much , please return FinalAnswer directly."""
    TIMEOUT: int = 60

    def __init__(
        self,
        http_method: str,
        url: str,
        query: dict | None = None,
        header: dict | None = None,
        body: dict | None = None,
        path: dict | None = None,
        max_retry: int = 3,
        complex_fields: list | None = None,
        builtin_fields: dict | None = None,
        extra: dict | None = None,
    ):
        self.session = requests.Session()
        self._method = http_method
        self._url = url
        self._query = query if query else {}
        self._header = header if header else {}
        self._body = body if body else {}
        self._path = path if path else {}
        self._max_retry = max_retry
        self._request_counter: Dict[str, int] = {}
        self._complex_fields = complex_fields
        self._builtin_fields = builtin_fields or {}
        self._extra = ToolExtra.model_validate(extra or {})

    def __call__(self, **kwargs):
        # 提取 config 和 state (如果通过 InjectedState 和 RunnableConfig 注入)
        runtime_config = kwargs.pop("config", None)
        runtime_state = kwargs.pop("state", None)

        if self._check_max_call(kwargs):
            return self.CALL_TOO_MUCH_PROMPT

        for k, v in kwargs.items():
            http_part, field = k.split("__", 1)
            if http_part == "query":
                self._query[field] = v
            elif http_part == "header":
                self._header[field] = v
            elif http_part == "path":
                self._path[field] = v
            else:
                self._body[field] = v

        # 补充内置变量
        context = self._build_render_context(runtime_config, runtime_state)
        self._header = {k: self._render_variables(v, context) for k, v in self._header.items()} if self._header else {}
        self._body = {k: self._render_variables(v, context) for k, v in self._body.items()} if self._body else {}
        self._query = {k: self._render_variables(v, context) for k, v in self._query.items()} if self._query else {}
        self._path = {k: self._render_variables(v, context) for k, v in self._path.items()} if self._path else {}
        self._load_body()
        if self._extra:
            if self._extra.query:
                self._query.update(self._extra.query)
            if self._extra.header:
                self._header.update(self._extra.header)
            if self._extra.body:
                self._body.update(self._extra.body)
            if self._extra.path:
                self._path.update(self._extra.path)

        # LLM填充url模版
        self._url = self._build_dynamic_url()

        try:
            resp = self.session.request(
                self._method,
                self._url,
                headers=self._header if self._header else None,
                params=self._query if self._query else None,
                json=self._body if self._body else None,
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            try:
                if resp.headers.get("content-type", "") == "application/json":
                    return resp.json()
                else:
                    return resp.text
            except JSONDecodeError:
                return resp.content
        except requests.HTTPError as err:
            return f"[HTTPError]: {err.response.content.decode()}"
        except Exception as err:
            return f"Request ERROR: {err}"

    def _load_body(self):
        for key in self._body:
            if key not in self._complex_fields or not isinstance(self._body[key], str):
                continue
            with contextlib.suppress(json.decoder.JSONDecodeError):
                self._body[key] = json.loads(self._body[key])

    def _check_max_call(self, requests: dict) -> bool:
        """检查同个请求是否请求多次"""
        if not requests:
            return False
        request_hash = md5(json.dumps(requests).encode()).hexdigest()
        if request_hash not in self._request_counter:
            self._request_counter[request_hash] = 1
        counter = self._request_counter[request_hash]
        if counter >= self._max_retry:
            return True
        self._request_counter[request_hash] += 1
        return False

    def _build_dynamic_url(self) -> str:
        """构建最终的URL，支持动态路径参数"""

        # 使用当前的路径参数状态（已经合并了默认值和LLM传入值）
        path_values = self._path

        # 检查是否有路径参数需要处理, 匹配大括号内的参数名
        pattern = r"\{([^}/]+)\}"
        required_params = re.findall(pattern, self._url)
        if not required_params:
            # 没有路径参数，直接返回原始URL
            return self._url

        # 检查是否有未填充的必需路径参数
        missing_params = [param for param in required_params if param not in path_values]
        if missing_params:
            raise ValueError(f"缺少必须的路径参数: {', '.join(missing_params)}")

        # 替换路径参数
        result_url = self._url
        for param, value in path_values.items():
            if param and isinstance(param, str):
                result_url = result_url.replace(f"{{{param}}}", str(value))

        return result_url

    def _build_render_context(self, runtime_config: Optional[RunnableConfig], runtime_state: Optional[dict]) -> dict:
        """构建模板渲染上下文，包含 builtin_fields, state, config"""
        context = {}

        # 1. 添加内置字段 (向后兼容)
        if self._builtin_fields:
            context.update(self._builtin_fields)
            # 为了向后兼容，保留 bk_username 的特殊处理
            username = self._builtin_fields.get("username")
            if username:
                context["bk_username"] = username

        # 2. 添加 state (如果有注入)
        if runtime_state:
            context["state"] = runtime_state

        # 3. 添加 config (如果有注入)
        if runtime_config:
            context["config"] = runtime_config
            execute_kwargs = runtime_config.get("configurable", {}).get("execute_kwargs")
            if hasattr(execute_kwargs, "executor"):
                context["bk_username"] = execute_kwargs.executor
        return context

    def _render_variables(self, value: Any, context: dict):
        """使用 Jinja2 渲染变量，支持 builtin_fields, state, config"""
        if not isinstance(value, str):
            return value

        # 使用 jinja2_formatter 渲染模板
        try:
            rendered_value = jinja2_formatter(value, **context)
            return rendered_value
        except Exception as e:
            _logger.warning(f"Failed to render template '{value}': {e}")
            return value


def build_validator(name, rule: Rule):
    """基于字段验证动态构建pydantic的validator
    目前支持的方法：
    - 最大长度
    - 最小长度
    """

    def _max_length_check(v: str):
        value = int(rule.value) if isinstance(rule.value, str | float) else rule.value
        if len(v) > value:
            raise ToolValidationError(error_message=rule.message)
        return v

    def _min_length_check(v: str):
        if isinstance(rule.value, str) and len(v) < int(rule.value):
            raise ToolValidationError(error_message=rule.message)
        return v

    def _regexp(v: str):
        if isinstance(rule.value, str) and re.match(rule.value, v):
            raise ToolValidationError(error_message=rule.message)
        return v

    _mapping = {
        FuncType.MAX_LENGTH: _max_length_check,
        FuncType.MIN_LENGTH: _min_length_check,
        FuncType.REGEXP: _regexp,
    }
    return field_validator(name)(_mapping[rule.func])


def build_model(class_name: str, fields: list[BkField]) -> Type[BaseModel]:
    """动态创建 Pydantic 模型"""

    output_fields: Any = {}
    validators: dict[str, classmethod[Any, Any, Any]] = {}
    for field in fields:
        output_fields[field.name] = (
            field.get_python_type(),
            field.generate_field(),
        )
        if field.validates.enable:
            for rule in field.validates.rules:
                validator_name = f"{field.name}_{rule.func.value}_rule"
                validators[validator_name] = build_validator(field.name, rule)

    dynamic_model = create_model(class_name, __validators__=validators, **output_fields)
    return dynamic_model


def make_structured_tool(
    tool: Tool,
    debug: bool = False,
    builtin_fields: dict | None = None,
    inject_context: bool = True,
) -> StructuredTool:
    """根据Tool的ORM定义构建对应的langchain Tool
    注意的是会将嵌套的字段通过`__`打平,例如:
    ```json
    {
    "query": {"test": "123"}
    }
    ```
    对应的字段为: query__test=123

    Args:
        tool: Tool 定义
        debug: 是否开启调试模式
        builtin_fields: 内置字段，用于渲染模板变量
        inject_context: 是否注入上下文（包括 RunnableConfig 和 State），允许在工具中访问运行时配置和图状态
    """
    default_values: dict[str, dict[str, Any]] = {
        "header": {},
        "query": {},
        "body": {},
        "path": {},
    }
    complex_fields: list[str] = []
    _params: list[BkField] = []
    method = tool.method.lower()
    if method in ["get", "delete", "head"]:
        key_list = ["header", "query", "path"]
    elif method in ["post", "put", "patch"]:
        key_list = ["header", "body", "path"]
    else:
        key_list = ["header", "path"]
    for key in key_list:
        field_info = tool.property.get(key)
        default_values[key] = {}
        if not field_info:
            continue
        for each in field_info:
            if not each["name"]:
                continue
            each["validates"] = each.pop("validate", None)
            if each.get("default"):
                default_values[key][each["name"]] = each["default"]
            if each["type"] in COMPLEXED_FIELD_TYPE:
                complex_fields.append(each["name"])
            each["name"] = f"{key}__{each['name']}"
            _params.append(BkField(**each))
        if not _params:
            continue

    # 注意:不要在 _params 中添加 state 和 config,它们通过函数签名自动推断
    _model = build_model("_RequestInput", _params)

    def custom_handle_validation_error(__: ValidationError) -> str:
        return f"The input is not valid. Function schema is {_model.model_fields}"

    # 创建 ApiWrapper 实例
    api_wrapper = ApiWrapper(
        tool.method,
        tool.url,
        query=default_values.get("query", {}),
        header=default_values.get("header", {}),
        body=default_values.get("body", {}),
        path=default_values.get("path", {}),
        complex_fields=complex_fields,
        builtin_fields=builtin_fields,
        extra=tool.extra,
    )

    # 如果需要注入上下文（config 和 state），创建一个带注解的wrapper函数
    _tool = None
    if inject_context:
        try:
            from langgraph.prebuilt import InjectedState

            # 创建一个wrapper函数，同时支持 InjectedState 和 RunnableConfig 注入
            def tool_func(config: RunnableConfig = None, state: Annotated[dict, InjectedState] = None, **kwargs):
                # 将 config 和 state 传递给 ApiWrapper
                return api_wrapper(config=config, state=state, **kwargs)

            _tool = StructuredTool.from_function(
                func=tool_func,
                description=tool.description,
                return_direct=debug,
                name=tool.tool_code,
                args_schema=_model,
                handle_validation_error=custom_handle_validation_error if not debug else None,
                metadata={"tool_name": tool.tool_name},
            )

        except ImportError:
            _logger.warning("langgraph not installed, cannot inject context")
            # 降级到普通模式
    if _tool is None:
        # 不需要注入，直接使用 ApiWrapper
        _tool = StructuredTool.from_function(
            func=api_wrapper,
            description=tool.description,
            return_direct=debug,
            name=tool.tool_code,
            args_schema=_model,
            handle_validation_error=custom_handle_validation_error if not debug else None,
            metadata={"tool_name": tool.tool_name},
        )

    return _tool


def make_mcp_tools(server_config: dict, username: str | None = None) -> List[StructuredTool]:
    for _server_config in server_config.values():
        if _server_config.pop("credential_type", "") == CredentialType.BLUEAPPS.value:
            auth_info = {
                "bk_app_code": settings.APP_CODE,
                "bk_app_secret": settings.SECRET_KEY,
            }
            if username:
                if get_access_token_by_user:
                    auth_info = {"access_token": get_access_token_by_user(username).access_token}
                else:
                    auth_info = {"bk_username": username}
            _server_config["headers"] = {"X-Bkapi-Authorization": json.dumps(auth_info)}
            _server_config["headers"]["X-Bkapi-Timeout"] = settings.BK_APIGW_MCP_TIMEOUT

    _loop = get_event_loop()
    tools = []
    try:
        for server_name, _server_config in server_config.items():
            _logger.info(f"[make_mcp_tools] Connecting to MCP server: {server_name}")
            client = MultiServerMCPClient({server_name: _server_config})
            _tools: List[StructuredTool] = _loop.run_until_complete(client.get_tools())
            _logger.info(f"[make_mcp_tools] Got {len(_tools)} tools from {server_name}")
            for each in _tools:
                each.coroutine = wrap_mcp_exception(each.coroutine)
                if not each.metadata:
                    each.metadata = {}
                each.metadata["mcp_name"] = server_name
            tools.extend(_tools)
    except Exception as e:
        _logger.exception(f"[make_mcp_tools] 获取MCP工具列表失败: {e}")
        raise ValueError(f"获取MCP工具列表失败: {e}")
    return tools


def _extract_error_message(error_str: str) -> str:
    """从错误字符串中提取message"""
    match = re.search(r"(\{.*\})", error_str)
    if match:
        try:
            data = json.loads(match.group(1))
            return data.get("response_body", {}).get("message")
        except (json.JSONDecodeError, KeyError, AttributeError):
            # 如果JSON解析失败或预期的键不存在，则返回原始错误
            return error_str
    return error_str


def _extract_all_non_group_exceptions(exc):
    """递归提取 ExceptionGroup 中所有非-ExceptionGroup 的底层异常"""
    if isinstance(exc, BaseExceptionGroup):
        for e in exc.exceptions:
            yield from _extract_all_non_group_exceptions(e)
    else:
        yield exc


def wrap_mcp_exception(coro):
    """MCP异常处理包装器工厂函数

    Args:
        coro: 原始协程函数

    Returns:
        包装后的协程函数
    """

    async def wrapped_coro(*args, **kwargs):
        try:
            return await coro(*args, **kwargs)
        except ToolException as err:
            _logger.exception(f"failed to run mcp: {err}")
            # 尝试解析错误消息中的详细信息
            error_detail = _extract_error_message(str(err))
            return (f"[ERROR] MCP工具调用失败: {error_detail}", None)
        except BaseExceptionGroup as err:
            # 提取所有非 ExceptionGroup 的底层异常
            all_errors = list(_extract_all_non_group_exceptions(err))
            if all_errors:
                if len(all_errors) > 1:
                    error_lines = []
                    for i, e in enumerate(all_errors, start=1):
                        error_lines.append(f"错误{i}: {type(e).__name__} - {e}")
                    return (f"MCP工具调用失败，发现{len(all_errors)}个错误:\n" + "\n".join(error_lines), None)
                elif len(all_errors) == 1:
                    return (f"MCP工具调用失败: {type(all_errors[0]).__name__} - {all_errors[0]}", None)
            else:
                return (f"[ERROR] MCP工具调用失败: {err}", None)
        except ConnectionError as err:
            _logger.exception(f"failed to run mcp: {err}")
            return (f"[ERROR] MCP工具调用失败: 连接异常 {err}", None)
        except TimeoutError as err:
            _logger.exception(f"failed to run mcp: {err}")
            return (f"[ERROR] MCP工具调用失败: 超时异常 {err}", None)
        except Exception as err:
            _logger.exception(f"failed to run mcp: {err}")
            return (f"[ERROR] MCP工具调用失败: {err}", None)

    return wrapped_coro
