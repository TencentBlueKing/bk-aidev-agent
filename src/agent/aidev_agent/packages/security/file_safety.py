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

文件读写拒绝清单（敏感路径防护）。

参考 hermes ``file_safety.py`` 思路，阻止 agent 通过运行时工具访问敏感路径
（SSH 密钥、云厂商凭据、gnupg、环境变量文件、凭据库等），防止密钥经工具结果
进入模型上下文或被外泄。

该模块与后端实现解耦，供 FilesystemBackend / PaasSandboxBackend / E2BSandboxBackend
在路径解析后统一调用 ``deny_reason`` 判定是否放行。
"""

from __future__ import annotations

import os
from pathlib import Path

# ========== 拒绝清单数据 ==========

# 敏感目录名：路径任一段命中即拒绝（含嵌套，如 /workspace/.ssh/id_rsa）
SENSITIVE_DIRS = frozenset(
    {
        ".ssh",
        ".gnupg",
        ".aws",
        ".azure",
        ".gcp",
        ".kube",
    }
)

# 多段敏感目录（含分隔符的路径片段，如 .config/gh），按路径子串匹配
SENSITIVE_MULTI_SEGMENT_DIRS = (".config/gh", ".local/share/gh")

# 敏感文件/目录名（精确匹配 basename）
SENSITIVE_BASENAMES = frozenset(
    {
        "authorized_keys",
        "known_hosts",
        "credentials",
        "credentials.json",
        ".netrc",
        ".pgpass",
        ".git-credentials",
        ".htpasswd",
    }
)

# 敏感扩展名（小写）
SENSITIVE_SUFFIXES = (".pem", ".p12", ".pfx", ".key", ".keystore", ".jks", ".ppk", ".p8")

# 私钥文件名前缀（id_rsa / id_ed25519 / id_ecdsa / id_dsa 及 .pub 变体）
_PRIVATE_KEY_PREFIXES = ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")

# 强信号凭据关键字（出现在 basename 中即拒绝；刻意排除 tokenize/tokenizer 等良性词）
SENSITIVE_KEYWORDS = (
    "private_key",
    "api_key",
    "apikey",
    "access_token",
    "secret_key",
    "app_secret",
    "client_secret",
)


def _is_env_file(basename: str) -> bool:
    """匹配 .env 及其变体（.env.local / .env.production / .env.staging 等）。"""
    return basename == ".env" or basename.startswith(".env.")


def _is_private_key_file(basename: str) -> bool:
    """匹配私钥文件名（id_rsa / id_ed25519 / id_ecdsa / id_dsa 及 .pub 变体）。"""
    stem = basename
    if stem.endswith(".pub"):
        stem = stem[: -len(".pub")]
    return stem in _PRIVATE_KEY_PREFIXES


def _match_reason(normalized: str) -> str | None:
    """在规范化绝对路径上匹配拒绝清单，命中返回原因字符串，否则 None。"""
    parts = [p for p in normalized.split(os.sep) if p]
    for part in parts:
        if part in SENSITIVE_DIRS:
            return f"命中敏感目录 {part}"

    # 多段敏感目录（.config/gh 等），按路径子串匹配
    for mdir in SENSITIVE_MULTI_SEGMENT_DIRS:
        if normalized == mdir or normalized.startswith(mdir + os.sep) or f"{os.sep}{mdir}" in normalized:
            return f"命中敏感目录 {mdir}"

    basename = parts[-1] if parts else ""
    lower = basename.lower()

    if basename in SENSITIVE_BASENAMES:
        return f"命中敏感文件 {basename}"
    if _is_env_file(basename):
        return "命中环境变量文件 .env"
    if _is_private_key_file(basename):
        return f"命中私钥文件 {basename}"
    if lower.endswith(SENSITIVE_SUFFIXES):
        return f"命中敏感扩展名 {os.path.splitext(lower)[1]}"

    for kw in SENSITIVE_KEYWORDS:
        if kw in lower:
            return f"文件名包含敏感关键字 {kw}"

    return None


def deny_reason(path: str | os.PathLike | Path) -> str | None:
    """判断路径是否命中敏感拒绝清单。

    Args:
        path: 待检查的文件/目录路径（绝对或相对，含 `~`）。

    Returns:
        命中时返回中文拒绝原因；未命中返回 ``None``。
    """
    raw = os.fspath(path)
    if not raw:
        return None
    expanded = os.path.expanduser(raw)
    # normpath 规范化分隔符与冗余段，不 resolve 符号链接（后端另有 O_NOFOLLOW 防跳转）
    normalized = os.path.normpath(expanded)
    return _match_reason(normalized)


def is_sensitive_path(path: str | os.PathLike | Path) -> bool:
    """路径是否命中敏感拒绝清单（布尔判定）。"""
    return deny_reason(path) is not None


__all__ = [
    "SENSITIVE_DIRS",
    "SENSITIVE_BASENAMES",
    "SENSITIVE_SUFFIXES",
    "SENSITIVE_KEYWORDS",
    "deny_reason",
    "is_sensitive_path",
]
