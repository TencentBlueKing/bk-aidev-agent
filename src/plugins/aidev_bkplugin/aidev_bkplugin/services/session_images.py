# -*- coding: utf-8 -*-
"""历史读响应上的会话图片签发。只改调用方传入的列表，不回写平台。"""

from collections.abc import Callable

from aidev_agent.services.sandbox_pv_files import (
    SandboxPvFileService,
    fill_markdown_pv_image_urls,
    has_markdown_pv_image,
)


def sign_history_markdown_images(
    contents,
    session_code: str,
    file_service_factory: Callable[[], SandboxPvFileService],
) -> None:
    """有 Markdown 会话 PV 图片时才构造文件服务并签发。用户图片已由 OpenAPI 读路径刷新。"""
    if not session_code or not isinstance(contents, list):
        return
    if not any(
        isinstance(item, dict) and isinstance(item.get("content"), str) and has_markdown_pv_image(item["content"])
        for item in contents
    ):
        return
    file_service = file_service_factory()
    url_cache: dict[tuple[str, str], str] = {}
    for item in contents:
        content = item.get("content") if isinstance(item, dict) else None
        if isinstance(content, str):
            item["content"] = fill_markdown_pv_image_urls(
                file_service,
                content,
                url_cache=url_cache,
                session_code=session_code,
            )
