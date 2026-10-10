# -*- coding: utf-8 -*-
"""aidev_agent.core.tools.runtime_tools.types

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

运行时后端共享数据类型定义。

该模块包含所有运行时后端（local/e2b/paas）共享的类型合约：
- ls/glob 返回的 FileInfo
- grep 返回的 GrepMatch
- read 返回的 ReadResult
- write/edit/execute 返回的结果结构
- upload/download 返回的结构
- 延迟销毁记录共享存储抽象契约 RuntimeBackendDeferStore（内存实现见 defer_manager）

注意：该模块不包含任何具体后端实现。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from langchain_core.runnables import RunnableConfig
from typing_extensions import NotRequired, TypedDict

from aidev_agent.packages.security.redaction.policy import RedactionPurpose
from aidev_agent.pydantic_models import SecurityRedactionSettings


def _settings_digest(settings: SecurityRedactionSettings) -> str:
    """对**脱敏策略**取摘要，刻意排除 ``known_sensitive_values``。

    ``known_sensitive_values`` 会被 provider 按 backend 逐次合并（见
    ``provider._merge_known_values``），故它在签发侧与校验侧天然不同。
    把它算进摘要会让凭据恒不匹配、跳过逻辑静默失效（空 PEM 块又被误遮）。
    已知值本身仍需覆盖 —— 但它们已体现在 ``content_digest`` 里：合并值不同
    就会产出不同的脱敏结果，摘要随之不匹配。
    """
    payload = settings.model_dump(mode="json")
    payload.pop("known_sensitive_values", None)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


@dataclass(frozen=True)
class _RuntimeRedactionReceipt:
    """进程内结果凭据：只证明这份内容已按同一配置在格式化前处理。

    防伪来自 ``content_digest`` —— 外层工具若要伪造，必须让内容与**同一配置**下
    脱敏后的结果一致，而那时它已经做了脱敏，跳过重扫正是期望行为。
    ``settings_digest`` 另行保证「配置变更后旧凭据失效」。
    """

    content_digest: str
    settings_digest: str
    purpose: RedactionPurpose = RedactionPurpose.MODEL_OUTPUT

    @classmethod
    def create(cls, content: str, settings: SecurityRedactionSettings) -> _RuntimeRedactionReceipt:
        return cls(hashlib.sha256(content.encode()).hexdigest(), _settings_digest(settings))

    def matches(self, content: str, settings: SecurityRedactionSettings) -> bool:
        return (
            self.purpose == RedactionPurpose.MODEL_OUTPUT
            and self.content_digest == hashlib.sha256(content.encode()).hexdigest()
            and self.settings_digest == _settings_digest(settings)
        )


@dataclass
class ReadResult:
    """读取文件成功时返回的**原始行数据**。

    后端只负责「按原文件 offset/limit 选行」，**不做任何展示修饰**：
    行号、脱敏都在 provider 层统一处理（先脱敏、后加行号）。

    无损还原契约（provider 与后端的接口约定）：
    调用方以 ``"\\n".join(lines)`` 取回片段原文，脱敏后 ``split("\\n")``
    再切开，最后交给 :func:`~aidev_agent.core.tools.runtime_tools.utils.format_content_with_line_numbers`。
    因此 ``lines`` 必须满足 ``"\\n".join(lines).split("\\n") == lines`` ——
    即用 ``split("\\n")`` 而非 ``splitlines()`` 切分（后者会丢掉末尾空行，
    也会把 ``\\r`` / ``\\x0b`` 等当成行界）。典型用例：

    - 文件 ``"x\\n\\n"`` 选中整段 ⇒ ``lines == ["x", "", ""]``（2 个 LF ⇒ 3 行），
      ``start_line == 1``；
    - 片段为单个空行 ⇒ ``lines == [""]``；
    - ``offset=2`` ⇒ ``start_line == 3``（原文件中的真实 1-based 行号）。

    注：PaaS 后端由远端 ``awk print $0`` 逐行产出，文件末尾那个换行是**行终止符**
    而非独立一行，故其 ``lines`` 不含该终止符产生的末尾空串 ——
    两种行模型都满足上面的不动点，且都不丢真实空行。

    Attributes:
        lines: 选定片段的原始行（**不含行号**）；末行为空时以空串结尾。
        start_line: 片段首行在原文件中的 1-based 行号。
    """

    lines: list[str]
    start_line: int


class FileInfo(TypedDict):
    """文件信息结构。

    用于 ls_info 和 glob_info 方法返回的文件元数据。
    只有 path 是必需的，其他字段根据后端能力可选提供。
    """

    path: str
    """文件或目录的路径"""

    is_dir: NotRequired[bool]
    """是否为目录"""

    size: NotRequired[int]
    """文件大小（字节）"""

    modified_at: NotRequired[str]
    """最后修改时间（ISO 8601 格式）"""


class GrepMatch(TypedDict):
    """grep 搜索匹配结果结构。"""

    path: str
    """匹配的文件路径"""

    line: int
    """匹配的行号"""

    text: str
    """匹配的行内容"""


@dataclass
class WriteResult:
    """写操作结果。

    Attributes:
        error: 失败时的错误信息，成功时为 None
        path: 写入的文件路径，失败时为 None
        files_update: 文件更新信息，外部存储时为 None
    """

    error: str | None = None
    path: str | None = None
    files_update: dict | None = None


@dataclass
class EditResult:
    """编辑操作结果。

    Attributes:
        error: 失败时的错误信息，成功时为 None
        path: 编辑的文件路径，失败时为 None
        occurrences: 替换的匹配数量，失败时为 None
        files_update: 文件更新信息，外部存储时为 None
    """

    error: str | None = None
    path: str | None = None
    occurrences: int | None = None
    files_update: dict | None = None


@dataclass
class ExecuteResult:
    """命令执行结果。

    Attributes:
        output: 命令的标准输出和标准错误的合并输出
        exit_code: 命令退出码，None 表示执行过程中发生错误
        truncated: 输出是否因大小限制被截断
    """

    output: str
    exit_code: int | None = None
    truncated: bool = False


class FileUploadResponse(TypedDict):
    """文件上传响应结构。"""

    path: str
    """上传的文件路径"""

    error: str | None
    """错误信息，成功时为 None"""


class FileDownloadResponse(TypedDict):
    """文件下载响应结构。"""

    path: str
    """下载的文件路径"""

    content: bytes | None
    """文件内容，失败时为 None"""

    error: str | None
    """错误信息，成功时为 None"""


class RuntimeBackend:
    """运行时后端基类，提供统一的方法签名和生命周期管理接口。

    所有运行时后端（PaasSandboxBackend、E2BSandboxBackend、FilesystemBackend）
    应继承此基类，以支持统一的方法签名和上下文管理器协议。

    子类可根据需要重写 ``close()`` 方法以实现自定义清理逻辑。
    对于远程沙箱后端，``close()`` 通常调用 ``kill()`` 销毁远程实例。
    """

    # --- 文件操作方法（子类应重写） ---

    def ls_info(self, path: str, *, config: RunnableConfig | None = None, state: dict | None = None) -> list[FileInfo]:
        raise NotImplementedError

    def read(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
        *,
        config: RunnableConfig | None = None,
        state: dict | None = None,
    ) -> ReadResult | str:
        """读取文件并返回选定片段的**原始行数据**（不做展示修饰）。

        成功时返回 :class:`ReadResult`（原始行 + 原文件 1-based 起始行号），
        行号由 provider 统一在脱敏之后添加。

        返回 ``str`` 的既有返回型诊断（缺文件、偏移越界、空文件提示）保持不变；
        各后端原有的**抛异常**分支（如 PaaS 的 ``FileNotFoundError`` /
        ``IndexError``）同样保持抛异常语义。

        选行必须用 ``content.split("\\n")`` 而非 ``splitlines()`` ——
        后者会丢掉片段末尾的空行，破坏 ``"\\n".join(lines)`` 的无损往返
        （见 :class:`ReadResult`）。

        Args:
            file_path: 文件路径。
            offset: 起始行号（0-indexed）。
            limit: 最大读取行数。
            config: LangGraph 运行时配置（透传）。
            state: LangGraph 状态（透传）。
        """
        raise NotImplementedError

    def write(
        self, file_path: str, content: str, *, config: RunnableConfig | None = None, state: dict | None = None
    ) -> WriteResult:
        raise NotImplementedError

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        *,
        config: RunnableConfig | None = None,
        state: dict | None = None,
    ) -> EditResult:
        raise NotImplementedError

    def glob_info(
        self, pattern: str, path: str = "/", *, config: RunnableConfig | None = None, state: dict | None = None
    ) -> list[FileInfo]:
        raise NotImplementedError

    def grep_raw(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        config: RunnableConfig | None = None,
        state: dict | None = None,
    ) -> list[GrepMatch] | str:
        raise NotImplementedError

    def execute(
        self,
        command: str,
        timeout: int = 120,
        max_output_size: int = 100000,
        *,
        config: RunnableConfig | None = None,
        state: dict | None = None,
    ) -> ExecuteResult:
        raise NotImplementedError

    async def aexecute(
        self,
        command: str,
        timeout: int = 120,
        max_output_size: int = 100000,
        *,
        config: RunnableConfig | None = None,
        state: dict | None = None,
    ) -> ExecuteResult:
        raise NotImplementedError

    # --- 生命周期管理 ---

    def close(self) -> None:
        """释放后端持有的资源。

        默认实现为空操作。远程沙箱后端应重写此方法以销毁远程实例。
        此方法应是幂等的 — 多次调用不应产生副作用。
        """

    async def aclose(self) -> None:
        """异步释放后端持有的资源。

        默认实现委托给同步的 close()。子类可重写以提供更高效的异步实现。
        """
        self.close()

    # --- 沙箱复用序列化契约（save/load） ---

    def save(self) -> dict:
        """导出当前 backend 挂载所需 payload（写入共享存储，不含任何凭据）。

        子类必须重写。调用时机：请求结束时由 resolver 的 close 经 defer →
        store.put 登记沙箱（token 由 defer 管理器生成并持有）；lazy 后端在远端
        沙箱尚未创建时应抛异常（无沙箱可登记）。

        Returns:
            JSON 可序列化的挂载 payload 字典（如 sandbox_id / sandbox_info）。

        Raises:
            NotImplementedError: 子类未重写时抛出。
        """
        raise NotImplementedError

    def load(self, payload: dict) -> None:
        """挂载到 ``save()`` 导出的既有沙箱（实例方法，就地覆盖内部沙箱引用）。

        调用时机：``backend_cls(**construct_params)`` 先构造全新实例（lazy，
        尚无远端沙箱），原沙箱未被销毁时由 resolver 调 ``backend.load(payload)``
        挂载到原沙箱，后续首次使用跳过创建。client/凭据保持本实例构造时来源。

        Args:
            payload: 由 ``save()`` 产出的 dict。

        Raises:
            NotImplementedError: 子类未重写时抛出。
        """
        raise NotImplementedError

    def __enter__(self) -> "RuntimeBackend":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    async def __aenter__(self) -> "RuntimeBackend":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()


class RuntimeBackendDeferStore(Protocol):
    """沙箱延迟销毁记录共享存储抽象契约（4 原语 token 化，跨 pod 复用）。

    供上层应用（django cache / MySQL / Redis）实现；内存实现
    ``RuntimeBackendDeferInMemoryStore`` 见 ``defer_manager`` 模块。

    记录 schema 统一为 ``{"payload": dict, "token": str | None, "last_access_at": float}``。
    payload 为 ``backend.save()`` 产出的 JSON 可序列化挂载 dict（如
    ``{"sandbox_id": ...}``），不含任何凭据；token 由调用方（DeferManager 用
    ``uuid4()`` 生成）经 ``put`` 写入，store 保持哑存储、不自行生成 token。
    调用方（defer_manager/provider）不做任何状态判断，仅通过四个语义化原语交互：

    - ``get``：记录存在则返回 payload 并**原子摘除 token**（置 None）+ 刷新
      last_access_at；token 已为 None 时照常返回 payload；不创建记录；
    - ``put``：upsert 整体覆盖记录（payload + token + last_access_at=now）；
    - ``delete_if_token``：**原子 compare-and-delete**——仅当记录存在且记录内
      token 与参数相等才删记录返回 True，否则不动记录返回 False；
    - ``delete_expired``：GC 直接删除超 max_age 的记录（不 close 实例
      —— 超过阈值的记录其远端沙箱早已被平台 TTL 回收）。

    原子性硬契约：``get`` 的摘 token 与 ``delete_if_token`` 的比较删除必须在
    store 内部串行。InMemory 实现用 ``threading.Lock`` 保证；将来接入 Redis /
    SQL 时分别用 Lua 脚本 / 条件 UPDATE 复刻，不可拆分到应用层。
    """

    def get(self, key: str) -> dict | None:
        """记录存在则返回 payload（深拷贝），不存在返回 None；**不创建记录**。

        ``get`` 表示有 Agent 复用该沙箱：返回 payload 的同时**原子摘除记录内
        token**（置 None）+ 刷新 last_access_at=now。token 被摘除后，任何旧 entry
        的 ``delete_if_token`` 必失败（token 已为 None），旧记录永远无法被 close
        销毁 —— 这彻底关闭「turn 时长超 idle_ttl 被误杀」窗口，无需心跳。
        token 已为 None（并发挂载场景）时照常返回 payload。
        """
        ...

    def put(self, key: str, payload: dict, token: str) -> None:
        """upsert：整体覆盖记录（payload + token + last_access_at=now）。

        token 由调用方生成（DeferManager 用 ``uuid4()`` 生成后传入），store 保持
        哑存储、不自行生成 token。同 key 再次 put 用新 token/payload 覆盖旧记录
        （旧 token 失效 —— 旧 entry 的 delete_if_token 因此必失败）。"""
        ...

    def delete_if_token(self, key: str, token: str) -> bool:
        """原子 compare-and-delete：仅当记录存在且记录内 token 与参数相等时删除
        记录返回 True；否则（记录不存在 / 记录内 token 与参数不等 / token 已摘除
        为 None / 已被新 put 覆盖）不动记录返回 False。"""
        ...

    def delete_expired(self, max_age: float) -> int:
        """GC：直接删除 now-last_access_at > max_age 的记录（不做二阶段、不 close
        实例 —— 超过阈值的记录其远端沙箱早已被平台 TTL 回收）。返回删除条数。"""
        ...


__all__ = [
    "FileInfo",
    "GrepMatch",
    "ReadResult",
    "WriteResult",
    "EditResult",
    "ExecuteResult",
    "FileUploadResponse",
    "FileDownloadResponse",
    "RuntimeBackend",
    "RuntimeBackendDeferStore",
]
