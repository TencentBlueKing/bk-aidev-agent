# -*- coding: utf-8 -*-
"""read_image 工具测试共享 fixture。"""

import json
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.tools.runtime_tools.local_backend import FilesystemBackend
from aidev_agent.core.tools.runtime_tools.provider import RuntimeBackendResolver
from langchain_core.messages import AIMessage

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"
VISION_JSON = json.dumps(
    {"summary": "报错截图", "text": "ModuleNotFoundError: No module named 'xxx'"}, ensure_ascii=False
)


@pytest.fixture
def real_backend(tmp_path):
    """真实 FilesystemBackend（root_dir 指向 tmp_path），可写入真实图片字节。"""
    return FilesystemBackend(root_dir=str(tmp_path))


@pytest.fixture
def resolver(tmp_path):
    """已注册 local 与 paas_sandbox_my-skill 两个 runtime 的解析器（后者指向同一目录）。"""
    return (
        RuntimeBackendResolver(default_runtime="local")
        .register_runtime("local", FilesystemBackend(root_dir=str(tmp_path)))
        .register_runtime("paas_sandbox_my-skill", FilesystemBackend(root_dir=str(tmp_path)))
    )


@pytest.fixture
def vision_llm():
    """视觉模型 mock：invoke 返回 AIMessage(JSON 字符串)。"""
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content=VISION_JSON)
    return llm


@pytest.fixture
def to_image_uri():
    """把真实绝对路径折成工具入参 image_uri（默认 runtime=local）。"""

    def _build(real_path: str, runtime: str = "local") -> str:
        return f"file://{runtime}{real_path}"

    return _build
