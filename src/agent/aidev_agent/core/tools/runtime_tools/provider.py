# -*- coding: utf-8 -*-
"""aidev_agent.core.tools.runtime_tools.provider

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

运行时中间件与客户端工具构造。

本模块提供：
- `RuntimeBackendResolver`：运行时解析器（注册运行时、按 runtime 解析 backend、提供参数描述）
- `get_xxx_tool(...)`：构造单个工具（ls/read_file/.../execute）
- `get_client_tools(...)`：构造一组客户端工具（固定 7 个）

每个工具都暴露必填的 `target_runtime` 参数，用于指定目标运行时。

注意：参数名不能使用 `runtime`，因为 LangGraph ToolNode 会将名为 `runtime` 的参数
自动识别为注入点并注入 `ToolRuntime` 对象，与我们的字符串类型冲突。

注意：本模块只实现运行时路由与工具构造，不引入新的后端实现。
"""

from __future__ import annotations

import contextlib
import logging
from typing import Annotated, Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.prebuilt import InjectedState

from aidev_agent.config import settings

from .security import redact_output, validate_command, validate_path
from .types import RuntimeBackend
from .utils import format_grep_matches, truncate_if_too_long

logger = logging.getLogger(__name__)

# ========== 默认配置 ==========

DEFAULT_READ_OFFSET = 0
DEFAULT_READ_LIMIT = 100


# ========== 空输出提示 ==========

_EMPTY_OUTPUT_HINT = "[harness]该指令没有输出，可能是因为沙箱未能正确执行或者命令没有输出，请重试或者使用其他命令"


def _ensure_non_empty(value: str) -> str:
    """确保返回值非空，空字符串时返回友好提示。"""
    if not value or not value.strip():
        return _EMPTY_OUTPUT_HINT
    return value


def _get_sensitive_values(backend: RuntimeBackend | str) -> list[str]:
    """融合 SBX_SENSITIVE_VALUES 与 backend 的额外敏感值。"""
    values = list(settings.SBX_SENSITIVE_VALUES)
    if hasattr(backend, "extra_sensitive_values"):
        values.extend(backend.extra_sensitive_values)
    return values


# ========== 工具描述常量 ==========

LIST_FILES_TOOL_DESCRIPTION = """列出目录中的所有文件。用于浏览文件系统并找到需要读取或编辑的文件。"""

READ_FILE_TOOL_DESCRIPTION = """从文件系统读取文件。
如果用户提供了文件路径，假设该路径是有效的。读取不存在的文件是允许的；工具会返回错误信息。

用法：
- **重要（大文件与代码库探索）**：使用 offset / limit 参数分页，避免上下文溢出
- 首次扫描：read_file(path, limit=100) 查看文件结构
- 继续读取：read_file(path, offset=100, limit=200) 读取后续 200 行
- 仅在确有必要编辑时才省略 limit（读取全文件）
- 显式指定 offset 与 limit：read_file(path, offset=0, limit=100) 读取前 100 行
- 返回结果使用 cat -n 格式，行号从 1 开始
- 单行超过 5,000 字符会被拆分为多行并附带续行标记（如 5.1、5.2）。当你指定 limit 时，这些续行也计入 limit。
- 你可以在一次回复中调用多个工具；通常最好批量读取多个可能有用的文件
- 如果读取到的文件存在但内容为空，会返回 system reminder 提示"""

WRITE_FILE_TOOL_DESCRIPTION = """在文件系统中新建文件并写入内容。
用法：
- write_file 会创建一个新文件
- 如无必要，优先使用 edit_file 编辑已有文件，尽量避免创建新文件
"""

EDIT_FILE_TOOL_DESCRIPTION = """对文件执行精确字符串替换。
用法：
- 编辑前必须先读取文件；若未读取就尝试编辑，工具会报错
- 编辑时请严格保留 read 输出中的缩进（tab/space）。old_string / new_string 中不要包含行号前缀
- 总是优先编辑已有文件，而不是创建新文件
- 仅在用户明确要求时才使用表情符号
"""

GLOB_TOOL_DESCRIPTION = """按 glob 模式查找文件。
支持标准 glob 模式：`*`（任意字符）、`**`（任意目录）、`?`（单个字符）。
返回匹配该模式的绝对路径列表。
示例：
- `**/*.py` - 查找所有 Python 文件
- `*.txt` - 查找根目录下的所有文本文件
- `/subdir/**/*.md` - 查找 /subdir 下的所有 Markdown 文件"""

GREP_TOOL_DESCRIPTION = """在多个文件中搜索文本模式。
按字面文本（非正则）进行搜索，并根据 output_mode 返回匹配的文件列表或内容。
示例：
- 搜索所有文件：`grep(pattern="TODO")`
- 仅搜索 Python 文件：`grep(pattern="import", glob="*.py")`
- 展示匹配行：`grep(pattern="error", output_mode="content")`"""

EXECUTE_TOOL_DESCRIPTION = """执行 shell 命令。
用法：
执行给定命令，并进行必要的处理与安全措施。

在执行命令前，请遵循以下步骤：
1. 目录确认：
   - 如果命令会创建新目录或新文件，请先使用 ls 确认父目录存在且位置正确
   - 例如，在运行 "mkdir foo/bar" 之前，先用 ls 检查 "foo" 是否存在且为目标父目录
2. 命令执行：
   - 对包含空格的路径始终使用双引号（例如：cd "path with spaces/file.txt"）
   - 正确示例：
     - cd "/Users/name/My Documents"
     - python "/path/with spaces/script.py"
   - 错误示例（会失败）：
     - cd /Users/name/My Documents
     - python /path/with spaces/script.py
   - 确认引用无误后再执行命令，并捕获输出

用法说明：
- 命令在隔离的沙箱环境中运行
- 返回合并后的 stdout/stderr，并附带退出码
- 输出过大时可能被截断
- 重要：请避免使用 find / grep 等命令进行搜索；改用 grep / glob 工具。避免使用 cat/head/tail 读取文件；改用 read_file 工具。
- 多条命令请使用 ';' 或 '&&' 分隔；不要使用换行（引号内换行除外）
- 当命令间存在依赖时使用 '&&'（例如："mkdir dir && cd dir"）
- 当只需要顺序执行且不关心前序失败时使用 ';'
- 尽量使用绝对路径，避免频繁 cd 来保持工作目录稳定

示例：
推荐：
- execute(command="pytest /foo/bar/tests")
- execute(command="python /path/to/script.py")
- execute(command="npm install && npm test")

避免：
- execute(command="cd /foo/bar && pytest tests") # 请改用绝对路径
- execute(command="cat file.txt")                # 请改用 read_file
- execute(command="find . -name '*.py'")         # 请改用 glob
- execute(command="grep -r 'pattern' .")         # 请改用 grep
"""


class RuntimeBackendResolver:
    """运行时中间件（运行时解析器）—— 纯路由层 + 沙箱挂载协调（CR4/CR5）。

    该类负责运行时的注册与解析，并把沙箱复用交给所持有的 RuntimeBackendDeferManager：
    - 注册多个命名运行时后端（register_runtime，同名同实例幂等 / 异实例抛错）
    - 根据 runtime 参数解析 backend（resolve_backend / _resolve_backend）
    - 提供 runtime 参数描述文本（runtime_param_description / _runtime_param_description）
    - 沙箱 get_or_create：先构造全新实例，原沙箱未销毁时经实例 ``load`` 挂载（CR）；
      runtime_id 由 ``compose_runtime_id`` 从 runtime_name 幂等推导（同一 name 恒为
      同一 runtime_id）；延迟销毁策略在 ``__init__`` 由 defer_manager + agent_code/
      session_code 一次性判定。

    三个名字的语义边界（不要混淆）：
    - ``runtime 类型名``：运行时类型标识（如 ``local`` / ``sandbox`` / ``paas_sandbox``），注册到 ``_backend_cls``
    （类型名 -> backend 类，运行时 **类型注册唯一事实源**）
    由 builder 的 ``enable_runtime_*`` 经 ``register_runtime_cls`` 注册
    ``get_or_create_backend`` 按此名查类构造实例
    - ``runtime_name``：模型可见的路由名（``{runtime}_{skill}``），注册到 ``_backends``（实例注册表），供工具 ``target_runtime`` 解析。
    - ``runtime_id``：沙箱生命周期标识（``{agent_code}:{session_code}:{runtime}_{skill}``，
      由 ``compose_runtime_id(runtime_name)`` 幂等产出），provider/lifecycle 层用它识别沙箱（get_runtime / defer 延迟销毁）。

    类型注册表与实例注册表解耦：``_backend_cls`` 只管「类型名 -> 类」的映射（builder 配置期注册）
    ``_backends`` 只管「runtime_name -> backend 实例」的实例路由（``_prepare_skills`` 运行时按需构造挂载）

    注意：本类不负责构造工具集合；工具构造由本模块的 get_xxx_tool / get_client_tools 等函数承担

    Args:
        default_runtime: 当未指定 runtime 参数时使用的默认运行时名称。
        defer_manager: RuntimeBackendDeferManager 实例（延迟销毁 + 会话级复用），可选。
        agent_code: 智能体代码（runtime_id 的 scoping 维度，由装配层构造时注入）。
        session_code: 会话代码（同上）。延迟销毁策略要求两者齐备 —— 无 scoping 的
            复用会命中其他会话/智能体的沙箱，实质导致越权。
    """

    def __init__(
        self,
        default_runtime: str = "local",
        *,
        defer_manager=None,
        agent_code: str | None = None,
        session_code: str | None = None,
    ) -> None:
        self._backends: dict[str, RuntimeBackend] = {}
        self._backend_cls: dict[str, type] = {}  # runtime 类型名 -> backend 类（唯一事实源）
        self._default_runtime = default_runtime
        self._exit_stack = contextlib.ExitStack()
        # scoping 维度（CR：仅经构造参数注入，禁止外部改写内部变量）；
        # 供 compose_runtime_id 幂等组合沙箱生命周期标识 runtime_id
        self._agent_code = agent_code
        self._session_code = session_code
        # CR：初始化时确定是否开启延迟销毁策略 —— defer_manager 就绪且
        # agent_code/session_code 齐备才开启；否则 close 立即销毁全部
        if defer_manager is not None and agent_code and session_code:
            self._defer_manager = defer_manager
            self._enable_deferred_destroy = True
        else:
            self._defer_manager = None
            self._enable_deferred_destroy = False

    @property
    def default_runtime(self) -> str:
        """默认运行时名称。"""

        return self._default_runtime

    def register_runtime(
        self,
        name: str,
        backend: RuntimeBackend,
    ) -> "RuntimeBackendResolver":
        """注册一个命名运行时后端。

        同一 name 不允许注册不同 backend 实例（沙箱复用语义下同一 runtime 槽位始终指向同一沙箱）：
        已注册同实例时幂等返回；已注册不同实例时抛出``ValueError``。

        Args:
            name: 运行时名称（模型可见路由名，``{runtime}_{skill}``； 工具 ``target_runtime`` 传该值解析 backend）
            backend: 对应运行时的后端实例

        Returns:
            self（便于链式调用）

        Raises:
            ValueError: name 为空，或该 name 已注册了不同的 backend 实例。
        """

        if not name:
            raise ValueError("runtime name must be non-empty")
        existing = self._backends.get(name)
        if existing is not None:
            if existing is backend:
                return self  # 幂等：同一实例重复注册
            raise ValueError(f"runtime '{name}' 已注册不同的 backend 实例")
        self._backends[name] = backend
        # 统一注册到 ExitStack，未启用延迟销毁时 resolver.close() 立即关闭全部
        if isinstance(backend, RuntimeBackend):
            self._exit_stack.enter_context(backend)
        return self

    def register_runtime_cls(
        self,
        name: str,
        cls: type | None,
    ) -> "RuntimeBackendResolver":
        """注册一个 runtime 类型名到 backend 类的映射（类型注册唯一事实源）。

        builder 配置期经 ``enable_runtime_*``/``register_runtime_type`` 调用
        把 runtime 类型名（如 ``local``/``sandbox``/``paas_sandbox``）映射到 backend类，供 ``get_or_create_backend`` 按名查类构造实例

        - ``cls`` 非 None：同名已注册**同一**类时幂等返回 self；已注册**不同**类时抛出 ``ValueError``（文案带当前冲突类名，便于定位）
        - ``cls`` 为 None：注销该类型名（``pop``，name 不存在时静默，无副作用）

        Args:
            name: runtime 类型名（非空）。
            cls: backend 类；None 表示注销该类型名。

        Returns:
            self（便于链式调用）

        Raises:
            ValueError: name 为空，或该 name 已注册了不同的 backend 类。
        """
        if not name:
            raise ValueError("runtime name must be non-empty")
        if cls is None:
            self._backend_cls.pop(name, None)  # 注销：pop 不存在的 name 静默
            return self
        existing = self._backend_cls.get(name)
        if existing is not None:
            if existing is cls:
                return self  # 幂等：同一类重复注册
            raise ValueError(f"runtime '{name}' 已注册不同的 backend 类 {existing.__name__}（现注册 {cls.__name__}）")
        self._backend_cls[name] = cls
        return self

    def have_runtime_cls(self, name: str) -> bool:
        """判断某 runtime 类型名是否已注册（替代 builder 侧 ``name in _runtime_types``）。

        Args:
            name: runtime 类型名（如 ``paas_sandbox``）。

        Returns:
            已注册返回 True，否则 False。
        """

        return name in self._backend_cls

    def runtime_param_description(self) -> str:
        """返回 runtime 参数的描述文本（用于工具 schema）。"""

        return self._runtime_param_description()

    def resolve_backend(self, runtime: str) -> RuntimeBackend | str:
        """解析 runtime 对应的后端；未指定时回退到默认运行时。"""

        return self._resolve_backend(runtime)

    def _runtime_param_description(self) -> str:
        names = sorted(self._backends.keys())
        joined = ", ".join(names) if names else "(none)"
        return f"运行此工具的目标运行时（必填）。可选值: {joined}。"

    def _resolve_backend(self, runtime: str) -> RuntimeBackend | str:
        resolved_runtime = runtime

        if resolved_runtime not in self._backends:
            available = ", ".join(sorted(self._backends.keys()))
            raise ValueError(f"Unknown runtime '{resolved_runtime}'. Available runtimes: {available or '(none)'}")

        backend = self._backends[resolved_runtime]
        return backend

    def get_or_create_backend(
        self,
        runtime_name: str,
        runtime_cls_name: str,
        construct_params: dict | None = None,
    ) -> RuntimeBackend:
        """获取/创建沙箱 backend（CR：先构造再挂载）。

        runtime_id 由 ``compose_runtime_id(runtime_name)`` 幂等推导（同一 name 恒为同一 runtime_id），不由外部传入。

        流程：
        1. 先按 ``runtime_cls_name`` 从 ``_backend_cls`` 查到 backend 类，再``backend_cls(**construct_params)`` 构造全新实例
            lazy： 后端此时尚无远端沙箱，client/凭据全部来自本次请求的构造参数
        2. 延迟销毁策略启用时（``__init__`` 判定），
            若原沙箱未被销毁，调用实例方法``backend.load(payload)`` 挂载到原沙箱，后续首次使用跳过创建；
           原沙箱已销毁/无记录时保持全新实例
           close 移交所有权后由 defer_manager``defer`` 登记新沙箱

        Args:
            runtime_name: 模型可见的路由名（``{runtime}_{skill}``），注册到 ``_backends`` 供工具 ``target_runtime`` 解析；runtime_id 由此幂等推导
            runtime_cls_name: runtime 类型名，须先经 ``register_runtime_cls`` 注册；内部据此从 ``_backend_cls`` 查类构造实例
            construct_params: 传给查到的 ``backend_cls(**construct_params)`` 的参数（含本次请求的 client/凭据）。

        Returns:
            已挂载原沙箱或全新待用的 backend 实例（注册到 self._backends[runtime_name]）。

        Raises:
            ValueError: ``runtime_cls_name`` 未注册（带当前注册表内容，便于定位
                误传的类名/未注册类型）。
        """
        construct_params = construct_params or {}
        backend_cls = self._backend_cls.get(runtime_cls_name)
        if backend_cls is None:
            raise ValueError(
                f"unknown runtime class '{runtime_cls_name}'. registered classes: {sorted(self._backend_cls)}"
            )
        runtime_id = self.compose_runtime_id(runtime_name)
        # 1. 先构造全新实例（lazy，不创建远端沙箱）
        backend = backend_cls(**construct_params)
        if self._enable_deferred_destroy:
            original = self._defer_manager.get_runtime(runtime_id=runtime_id)
            if original is not None:
                # 2a. 原沙箱未被销毁：挂载到原沙箱（payload 为 {} 表示原沙箱从未
                # 真正拉起过，load 为 no-op，backend 保持 lazy）；get 读即续期，
                # sweep 在 idle_ttl 内抢不到销毁权
                backend.load(original)
            # 2b. 原沙箱已销毁/无记录：保持全新实例，close 移交所有权后由
            # defer_manager defer 登记新沙箱
        self.register_runtime(runtime_name, backend)
        return backend

    def compose_runtime_id(self, name: str) -> str:
        """组合沙箱生命周期标识 runtime_id：``{agent_code}:{session_code}:{name}``。

        幂等：同一 name 恒产出同一 runtime_id。内部维度缺失（测试/CLI 未注入 agent_code/session_code）时回退原名
        此时延迟销毁策略在 ``__init__``已关闭

        Args:
            name: 模型可见路由名（``{runtime}_{skill}``）。

        Returns:
            完整沙箱生命周期标识。
        """
        if self._agent_code and self._session_code and name:
            return f"{self._agent_code}:{self._session_code}:{name}"
        return name

    def close(self) -> None:
        """关闭/移交所有已注册后端（语义随延迟销毁策略分流）。

        - 未启用延迟销毁：立即销毁全部（ExitStack 依次 ``close()``）。
        - 启用延迟销毁：所有权整体移交给 RuntimeBackendDeferManager（``defer``）
          save() 登记记录供后续请求挂载复用，实例由 defer_manager 持有TTL 到期或进程退出时才真实销毁
          移交后 ``_backends`` 清空

        此方法是幂等的 — 多次调用不会产生副作用。
        """
        if not self._enable_deferred_destroy:
            try:
                self._exit_stack.close()
            except Exception:
                logger.warning("RuntimeBackendResolver.close: 关闭后端资源失败", exc_info=True)
            finally:
                # 关闭后重建 ExitStack，使 close() 幂等
                self._exit_stack = contextlib.ExitStack()
            return
        # 延迟销毁：所有权整体移交 defer_manager（含 lazy 未创建的 backend，save() 导出 {} 照常登记），之后本 resolver 不再持有任何沙箱
        pending = self._backends
        self._backends = {}
        # ExitStack 不执行 close（所有权已移交），重建使 close() 幂等
        self._exit_stack = contextlib.ExitStack()
        runtime_id_map = {self.compose_runtime_id(name): backend for name, backend in pending.items()}
        self._defer_manager.defer(runtime_id_map)


# ========== 工具生成器函数 ==========
def get_ls_tool(resolver: RuntimeBackendResolver, custom_description: str | None = None) -> BaseTool:
    """生成 ls（列出文件）工具。"""

    tool_description = custom_description or LIST_FILES_TOOL_DESCRIPTION

    def ls(
        path: Annotated[str, "Absolute path to the directory to list. Must be absolute, not relative."],
        target_runtime: str,
        config: RunnableConfig,
        state: Annotated[dict, InjectedState] = None,
    ) -> str:
        """列出目录中的文件。"""

        resolved_backend = resolver.resolve_backend(target_runtime)

        validated_path = validate_path(path)
        infos = resolved_backend.ls_info(validated_path, config=config, state=state)
        paths = [fi.get("path", "") for fi in infos]
        result = truncate_if_too_long(paths)
        return redact_output(_ensure_non_empty(str(result)), _get_sensitive_values(resolved_backend))

    ls.__annotations__["target_runtime"] = Annotated[str, resolver.runtime_param_description()]

    return StructuredTool.from_function(
        name="ls",
        description=tool_description,
        func=ls,
    )


def get_read_file_tool(resolver: RuntimeBackendResolver, custom_description: str | None = None) -> BaseTool:
    """生成 read_file 工具。"""

    tool_description = custom_description or READ_FILE_TOOL_DESCRIPTION

    def read_file(
        file_path: Annotated[
            str,
            "Absolute path to the file to read. PaaS sandbox paths may start with $STORAGE_PATH/.",
        ],
        target_runtime: str,
        config: RunnableConfig,
        state: Annotated[dict, InjectedState] = None,
        offset: Annotated[int, "Line number to start reading from (0-indexed). Use for pagination of large files."] = (
            DEFAULT_READ_OFFSET
        ),
        limit: Annotated[int, "Maximum number of lines to read. Use for pagination of large files."] = (
            DEFAULT_READ_LIMIT
        ),
    ) -> str:
        """读取文件内容。"""

        resolved_backend = resolver.resolve_backend(target_runtime)

        validated_path = validate_path(file_path)
        result = resolved_backend.read(validated_path, offset=offset, limit=limit, config=config, state=state)
        lines = result.splitlines(keepends=True)
        if len(lines) > limit:
            lines = lines[:limit]
        return redact_output(_ensure_non_empty("".join(lines)), _get_sensitive_values(resolved_backend))

    read_file.__annotations__["target_runtime"] = Annotated[str, resolver.runtime_param_description()]

    return StructuredTool.from_function(
        name="read_file",
        description=tool_description,
        func=read_file,
    )


def get_write_file_tool(resolver: RuntimeBackendResolver, custom_description: str | None = None) -> BaseTool:
    """生成 write_file 工具。"""

    tool_description = custom_description or WRITE_FILE_TOOL_DESCRIPTION

    def write_file(
        file_path: Annotated[str, "Absolute path where the file should be created. Must be absolute, not relative."],
        content: Annotated[str, "The text content to write to the file. This parameter is required."],
        target_runtime: str,
        config: RunnableConfig,
        state: Annotated[dict, InjectedState] = None,
    ) -> str:
        """创建新文件。"""

        resolved_backend = resolver.resolve_backend(target_runtime)

        validated_path = validate_path(file_path)
        res = resolved_backend.write(validated_path, content, config=config, state=state)
        if res.error:
            raise ValueError(redact_output(_ensure_non_empty(res.error), _get_sensitive_values(resolved_backend)))
        return redact_output(_ensure_non_empty(f"Updated file {res.path}"), _get_sensitive_values(resolved_backend))

    write_file.__annotations__["target_runtime"] = Annotated[str, resolver.runtime_param_description()]

    return StructuredTool.from_function(
        name="write_file",
        description=tool_description,
        func=write_file,
    )


def get_edit_file_tool(resolver: RuntimeBackendResolver, custom_description: str | None = None) -> BaseTool:
    """生成 edit_file 工具。"""

    tool_description = custom_description or EDIT_FILE_TOOL_DESCRIPTION

    def edit_file(
        file_path: Annotated[str, "Absolute path to the file to edit. Must be absolute, not relative."],
        old_string: Annotated[
            str, "The exact text to find and replace. Must be unique in the file unless replace_all is True."
        ],
        new_string: Annotated[str, "The text to replace old_string with. Must be different from old_string."],
        target_runtime: str,
        config: RunnableConfig,
        state: Annotated[dict, InjectedState] = None,
        replace_all: Annotated[
            bool, "If True, replace all occurrences of old_string. If False (default), old_string must be unique."
        ] = (False),
    ) -> str:
        """通过字符串替换编辑文件。"""

        resolved_backend = resolver.resolve_backend(target_runtime)

        validated_path = validate_path(file_path)
        res = resolved_backend.edit(
            validated_path, old_string, new_string, replace_all=replace_all, config=config, state=state
        )
        if res.error:
            raise ValueError(redact_output(_ensure_non_empty(res.error), _get_sensitive_values(resolved_backend)))
        return redact_output(
            _ensure_non_empty(f"Successfully replaced {res.occurrences} instance(s) of the string in '{res.path}'"),
            _get_sensitive_values(resolved_backend),
        )

    edit_file.__annotations__["target_runtime"] = Annotated[str, resolver.runtime_param_description()]

    return StructuredTool.from_function(
        name="edit_file",
        description=tool_description,
        func=edit_file,
    )


def get_glob_tool(resolver: RuntimeBackendResolver, custom_description: str | None = None) -> BaseTool:
    """生成 glob 工具。"""

    tool_description = custom_description or GLOB_TOOL_DESCRIPTION

    def glob(
        pattern: Annotated[str, "Glob pattern to match files (e.g., '**/*.py', '*.txt', '/subdir/**/*.md')."],
        target_runtime: str,
        config: RunnableConfig,
        state: Annotated[dict, InjectedState] = None,
        path: Annotated[str, "Base directory to search from. Defaults to root '/'."] = "/",
    ) -> str:
        """查找匹配 glob 模式的文件。"""

        resolved_backend = resolver.resolve_backend(target_runtime)

        infos = resolved_backend.glob_info(pattern, path=path, config=config, state=state)
        paths = [fi.get("path", "") for fi in infos]
        result = truncate_if_too_long(paths)
        return redact_output(_ensure_non_empty(str(result)), _get_sensitive_values(resolved_backend))

    glob.__annotations__["target_runtime"] = Annotated[str, resolver.runtime_param_description()]

    return StructuredTool.from_function(
        name="glob",
        description=tool_description,
        func=glob,
    )


def get_grep_tool(resolver: RuntimeBackendResolver, custom_description: str | None = None) -> BaseTool:
    """生成 grep 工具。"""

    tool_description = custom_description or GREP_TOOL_DESCRIPTION

    def grep(
        pattern: Annotated[str, "Text pattern to search for (literal string, not regex)."],
        target_runtime: str,
        config: RunnableConfig,
        state: Annotated[dict, InjectedState] = None,
        path: Annotated[str | None, "Directory to search in. Defaults to current working directory."] = None,
        glob: Annotated[str | None, "Glob pattern to filter which files to search (e.g., '*.py')."] = None,
        output_mode: Annotated[
            Literal["files_with_matches", "content", "count"],
            "Output format: 'files_with_matches' (file paths only, default), 'content' (matching lines with context), 'count' (match counts per file).",
        ] = "files_with_matches",
    ) -> str:
        """在文件中搜索文本模式。"""

        resolved_backend = resolver.resolve_backend(target_runtime)

        raw = resolved_backend.grep_raw(pattern, path=path, glob=glob, config=config, state=state)
        if isinstance(raw, str):
            raise ValueError(redact_output(_ensure_non_empty(raw), _get_sensitive_values(resolved_backend)))
        formatted = format_grep_matches(raw, output_mode)
        return redact_output(
            _ensure_non_empty(truncate_if_too_long(formatted)), _get_sensitive_values(resolved_backend)
        )

    grep.__annotations__["target_runtime"] = Annotated[str, resolver.runtime_param_description()]

    return StructuredTool.from_function(
        name="grep",
        description=tool_description,
        func=grep,
    )


def get_execute_tool(
    resolver: RuntimeBackendResolver,
    custom_description: str | None = None,
    enable_security: bool | None = None,
) -> BaseTool:
    """生成 execute 工具用于执行 shell 命令。

    Args:
        resolver: 运行时解析器。
        custom_description: 自定义工具描述。
        enable_security: 是否启用命令安全校验。
            默认为 None 时启用校验（True）。
            设为 False 可完全跳过安全校验（仅用于测试或迁移过渡期）。
    """

    # 确定是否启用安全校验（默认启用）
    if enable_security is None:
        enable_security = True

    tool_description = custom_description or EXECUTE_TOOL_DESCRIPTION

    def execute(
        command: Annotated[str, "Shell command to execute in the sandbox environment."],
        target_runtime: str,
        config: RunnableConfig,
        state: Annotated[dict, InjectedState] = None,
    ) -> str:
        """在沙箱环境中执行 shell 命令。"""

        resolved_backend = resolver.resolve_backend(target_runtime)

        # 【新增】安全校验：命令白名单检查
        if enable_security:
            result = validate_command(command)
            if not result.is_allowed:
                raise ValueError(
                    redact_output(
                        _ensure_non_empty(f"命令执行被拒绝：{result.reason}"),
                        _get_sensitive_values(resolved_backend),
                    )
                )

        result = resolved_backend.execute(command, config=config, state=state)

        parts = [result.output]
        if result.truncated:
            parts.append("\n[Output was truncated due to size limits]")
        return redact_output(_ensure_non_empty("".join(parts)), _get_sensitive_values(resolved_backend))

    async def async_execute(
        command: Annotated[str, "Shell command to execute in the sandbox environment."],
        target_runtime: str,
        config: RunnableConfig,
        state: Annotated[dict, InjectedState] = None,
    ) -> str:
        """异步执行 shell 命令。"""

        resolved_backend = resolver.resolve_backend(target_runtime)

        # 【新增】安全校验：命令白名单检查
        if enable_security:
            result = validate_command(command)
            if not result.is_allowed:
                raise ValueError(
                    redact_output(
                        _ensure_non_empty(f"命令执行被拒绝：{result.reason}"),
                        _get_sensitive_values(resolved_backend),
                    )
                )

        result = await resolved_backend.aexecute(command, config=config, state=state)

        parts = [result.output]
        if result.truncated:
            parts.append("\n[Output was truncated due to size limits]")
        return redact_output(_ensure_non_empty("".join(parts)), _get_sensitive_values(resolved_backend))

    execute.__annotations__["target_runtime"] = Annotated[str, resolver.runtime_param_description()]
    async_execute.__annotations__["target_runtime"] = Annotated[str, resolver.runtime_param_description()]

    return StructuredTool.from_function(
        name="execute",
        description=tool_description,
        func=execute,
        coroutine=async_execute,
    )


# ========== 客户端工具集合 ==========


def get_client_tools_with_runtime(
    resolver: RuntimeBackendResolver,
    custom_tool_descriptions: dict[str, str] | None = None,
    enable_security: bool | None = None,
) -> list[BaseTool]:
    """构造客户端工具集合。

    返回固定 7 个工具：ls、read_file、write_file、edit_file、glob、grep、execute。

    Args:
        resolver: 运行时解析器（负责 runtime -> backend 路由）。
        custom_tool_descriptions: 可选的自定义工具描述字典，key 为工具名。
        enable_security: 是否启用 execute 工具的命令安全校验。
            默认为 None，从环境变量读取。设为 False 可跳过校验。

    Returns:
        LangChain 工具列表。
    """

    if custom_tool_descriptions is None:
        custom_tool_descriptions = {}

    return [
        get_ls_tool(resolver, custom_tool_descriptions.get("ls")),
        get_read_file_tool(resolver, custom_tool_descriptions.get("read_file")),
        get_write_file_tool(resolver, custom_tool_descriptions.get("write_file")),
        get_edit_file_tool(resolver, custom_tool_descriptions.get("edit_file")),
        get_glob_tool(resolver, custom_tool_descriptions.get("glob")),
        get_grep_tool(resolver, custom_tool_descriptions.get("grep")),
        get_execute_tool(resolver, custom_tool_descriptions.get("execute"), enable_security=enable_security),
    ]
