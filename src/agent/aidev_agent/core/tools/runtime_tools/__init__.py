# -*- coding: utf-8 -*-
"""运行时工具统一包（runtime_tools）。

该包合并了原有的 runtime_base/runtime_local/runtime_e2b/runtime_paas 四个子包，
集中存放运行时子系统的所有组件：
- 共享类型定义（types），含延迟销毁 store 抽象契约
- 共享工具函数（utils），含 skill 打包工具
- 运行时工具提供者与路由（provider）
- 沙箱延迟销毁：内存版 store 与 DeferManager（defer_manager）
- 本地文件系统后端（local_backend）
- E2B 远程沙箱后端（e2b_backend）
- PaaS 远程沙箱后端（paas_backend）
"""

from .defer_manager import RuntimeBackendDeferInMemoryStore, RuntimeBackendDeferManager
from .e2b_backend import E2BSandboxBackend
from .local_backend import FilesystemBackend
from .paas_backend import PaasSandboxBackend
from .provider import (
    RuntimeBackendResolver,
    get_client_tools_with_runtime,
    get_edit_file_tool,
    get_execute_tool,
    get_glob_tool,
    get_grep_tool,
    get_ls_tool,
    get_read_file_tool,
    get_write_file_tool,
)
from .types import (
    EditResult,
    ExecuteResult,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    RuntimeBackend,
    RuntimeBackendDeferStore,
    WriteResult,
)
from .utils import (
    EMPTY_CONTENT_WARNING,
    LINE_NUMBER_WIDTH,
    MAX_OUTPUT_LENGTH,
    FileData,
    FilesystemState,
    PathValidationError,
    check_empty_content,
    format_content_with_line_numbers,
    format_grep_matches,
    package_dir,
    perform_string_replacement,
    truncate_if_too_long,
    validate_path,
)

__all__ = [
    # provider
    "RuntimeBackendResolver",
    "get_ls_tool",
    "get_read_file_tool",
    "get_write_file_tool",
    "get_edit_file_tool",
    "get_glob_tool",
    "get_grep_tool",
    "get_execute_tool",
    "get_client_tools_with_runtime",
    # defer_manager
    "RuntimeBackendDeferInMemoryStore",
    "RuntimeBackendDeferManager",
    # types
    "FileInfo",
    "GrepMatch",
    "WriteResult",
    "EditResult",
    "ExecuteResult",
    "FileUploadResponse",
    "FileDownloadResponse",
    "RuntimeBackend",
    "RuntimeBackendDeferStore",
    # utils
    "EMPTY_CONTENT_WARNING",
    "LINE_NUMBER_WIDTH",
    "MAX_OUTPUT_LENGTH",
    "PathValidationError",
    "FileData",
    "FilesystemState",
    "validate_path",
    "check_empty_content",
    "format_content_with_line_numbers",
    "perform_string_replacement",
    "truncate_if_too_long",
    "format_grep_matches",
    "package_dir",
    # backends
    "FilesystemBackend",
    "E2BSandboxBackend",
    "PaasSandboxBackend",
]
