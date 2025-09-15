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
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, Field, ValidationError, create_model, field_validator
from requests.exceptions import JSONDecodeError

from aidev_agent.config import settings
from aidev_agent.core.utils.local import request_local
from aidev_agent.core.utils.loop import get_event_loop
from aidev_agent.enums import CredentialType
from aidev_agent.packages.langchain.exceptions import ToolValidationError
from aidev_agent.packages.langchain.tools.enums import FieldType, FuncType

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
        self._header = {k: self._render_builtin_variables(v) for k, v in self._header.items()} if self._header else {}
        self._body = {k: self._render_builtin_variables(v) for k, v in self._body.items()} if self._body else {}
        self._query = {k: self._render_builtin_variables(v) for k, v in self._query.items()} if self._query else {}
        self._path = {k: self._render_builtin_variables(v) for k, v in self._path.items()} if self._path else {}
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

    def _render_builtin_variables(self, value: Any):
        """内部变量暂时只支持渲染 bk_username"""
        if not isinstance(value, str):
            return value
        username = self._builtin_fields.get("username")
        value = jinja2_formatter(value, bk_username=f'"{username}"')
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
) -> StructuredTool:
    """根据Tool的ORM定义构建对应的langchain Tool
    注意的是会将嵌套的字段通过`__`打平,例如:
    ```json
    {
    "query": {"test": "123"}
    }
    ```
    对应的字段为: query__test=123
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

    _model = build_model("_RequestInput", _params)

    def custom_handle_validation_error(__: ValidationError) -> str:
        return f"The input is not valid. Function schema is {_model.model_fields}"

    _tool = StructuredTool.from_function(
        func=ApiWrapper(
            tool.method,
            tool.url,
            query=default_values.get("query", {}),
            header=default_values.get("header", {}),
            body=default_values.get("body", {}),
            path=default_values.get("path", {}),
            complex_fields=complex_fields,
            builtin_fields=builtin_fields,
            extra=tool.extra,
        ),
        description=tool.description,
        return_direct=debug,
        name=tool.tool_code,
        args_schema=_model,
        handle_validation_error=custom_handle_validation_error if not debug else None,
        metadata={"tool_name": tool.tool_name},
    )
    return _tool


def make_mcp_tools(server_config: dict) -> List[StructuredTool]:
    try:
        from bkoauth import get_access_token_by_user
    except ImportError:
        get_access_token_by_user = None

    for _server_config in server_config.values():
        if _server_config.pop("credential_type", "") == CredentialType.BLUEAPPS.value:
            auth_info = {
                "bk_app_code": settings.APP_CODE,
                "bk_app_secret": settings.SECRET_KEY,
            }
            request = getattr(request_local, "request", None)
            if request and request.user.username:
                if get_access_token_by_user:
                    auth_info = {"access_token": get_access_token_by_user(request.user.username).access_token}
                else:
                    auth_info["bk_username"] = request.user.username
            _server_config["headers"] = {"X-Bkapi-Authorization": json.dumps(auth_info)}

    client = MultiServerMCPClient(server_config)
    _loop = get_event_loop()
    try:
        tools: List[StructuredTool] = _loop.run_until_complete(client.get_tools())
    except Exception:
        raise ValueError("获取MCP工具列表失败")
    for each in tools:
        each.coroutine = MCPExceptionWrapper(each.coroutine)
    return tools


class MCPExceptionWrapper:
    """可序列化的MCP异常处理包装器"""

    def __init__(self, coro):
        self.coro = coro

    async def __call__(self, *args, **kwargs):
        try:
            return await self.coro(*args, **kwargs)
        except Exception as err:
            _logger.exception(f"failed to run mcp: {err}")
            return ("[ERROR] MCP工具调用失败", None)

    def __getstate__(self):
        # 在序列化时保存协程对象
        return {"coro": self.coro}

    def __setstate__(self, state):
        # 在反序列化时恢复协程对象
        self.coro = state["coro"]
