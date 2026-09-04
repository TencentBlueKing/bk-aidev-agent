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
- write/edit/execute 返回的结果结构
- upload/download 返回的结构
- 延迟销毁记录共享存储抽象契约 RuntimeBackendDeferStore（内存实现见 defer_manager）

注意：该模块不包含任何具体后端实现。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from langchain_core.runnables import RunnableConfig
from typing_extensions import NotRequired, TypedDict


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
    ) -> str:
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
    "WriteResult",
    "EditResult",
    "ExecuteResult",
    "FileUploadResponse",
    "FileDownloadResponse",
    "RuntimeBackend",
    "RuntimeBackendDeferStore",
]
