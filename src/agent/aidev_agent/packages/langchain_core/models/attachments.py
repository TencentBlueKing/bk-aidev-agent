"""附件内容的规范化与 provider（模型服务商）映射。"""

import base64
import mimetypes
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from aidev_agent.exceptions import AIDevException

_GENERIC_BINARY_MIME_TYPE = "application/octet-stream"
_DOCUMENT_MIME_TYPES = frozenset(
    {
        "application/epub+zip",
        "application/json",
        "application/msword",
        "application/rtf",
        "application/sql",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.oasis.opendocument.presentation",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.oasis.opendocument.text",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
        "application/xml",
        "application/x-yaml",
        "application/yaml",
    }
)
_DEFAULT_CAPABILITIES = {"image": True, "audio": False, "video": False}


@dataclass(frozen=True)
class CanonicalAttachment:
    """模型边界使用的统一附件描述。"""

    filename: str
    mime_type: str
    source_url: str
    extracted_text: str

    @property
    def kind(self) -> str:
        if self.mime_type.startswith("image/"):
            return "image"
        if self.mime_type.startswith("audio/"):
            return "audio"
        if self.mime_type.startswith("video/"):
            return "video"
        if self.mime_type.startswith("text/") or self.mime_type in _DOCUMENT_MIME_TYPES:
            return "document"
        return "unknown"


def normalize_mime_type(value: object) -> str:
    """清理 MIME（媒体类型）参数和大小写。"""
    if not isinstance(value, str):
        return ""
    return value.split(";", 1)[0].strip().lower()


def _guess_mime_type(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    mime_type, _ = mimetypes.guess_type(value)
    return mime_type or ""


def _get_data_url_mime_type(value: object) -> str:
    if not isinstance(value, str) or not value.lower().startswith("data:"):
        return ""
    return normalize_mime_type(value[5:].split(",", 1)[0].split(";", 1)[0])


def get_binary_mime_type(content: Mapping[str, object]) -> str:
    """从 canonical 字段、data URL 与名称推导附件 MIME。"""
    mime_type = normalize_mime_type(
        content.get("mime_type")
        or content.get("mimeType")
        or content.get("content_type")
        or content.get("contentType")
    )
    if mime_type and mime_type != _GENERIC_BINARY_MIME_TYPE:
        return mime_type

    url = content.get("url")
    url_path = urlparse(url).path.rstrip("/") if isinstance(url, str) else ""
    return (
        _get_data_url_mime_type(url)
        or _guess_mime_type(content.get("filename"))
        or _guess_mime_type(url_path)
        or mime_type
        or _GENERIC_BINARY_MIME_TYPE
    )


def _get_attachment_source_url(content: Mapping[str, object], mime_type: str) -> str:
    url = content.get("url")
    if isinstance(url, str) and url:
        return url

    data = content.get("data")
    if isinstance(data, str) and data:
        return f"data:{mime_type};base64,{data}"
    return ""


def _get_extracted_text(content: Mapping[str, object], mime_type: str) -> str:
    extracted_text = content.get("extracted_text") or content.get("extractedText")
    if isinstance(extracted_text, str) and extracted_text.strip():
        return extracted_text

    if not mime_type.startswith("text/"):
        return ""

    data = content.get("data")
    if not isinstance(data, str) or not data:
        return ""
    try:
        return base64.b64decode(data, validate=True).decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return ""


def canonicalize_binary_attachment(content: Mapping[str, object]) -> CanonicalAttachment:
    """将前端或历史中的 binary 附件归一为统一结构。"""
    filename = content.get("filename")
    return CanonicalAttachment(
        filename=filename if isinstance(filename, str) else "",
        mime_type=get_binary_mime_type(content),
        source_url=_get_attachment_source_url(content, get_binary_mime_type(content)),
        extracted_text=_get_extracted_text(content, get_binary_mime_type(content)),
    )


def _attachment_error(message: str) -> AIDevException:
    return AIDevException(message=f"不支持的附件：{message}")


def _require_user_attachment(role: object) -> None:
    if role != "user":
        raise _attachment_error("仅支持用户消息中的附件")


def _require_capability(capabilities: Mapping[str, bool], kind: str) -> None:
    if not capabilities.get(kind, False):
        raise _attachment_error(f"当前模型未声明 {kind} 输入能力")


def _attachment_to_provider_part(
    attachment: CanonicalAttachment,
    *,
    role: object,
    capabilities: Mapping[str, bool],
) -> dict[str, Any]:
    _require_user_attachment(role)

    if attachment.kind == "document":
        if not attachment.extracted_text:
            raise _attachment_error(
                f"{attachment.filename or attachment.mime_type} 尚未解析为文本，不能直接发送给模型"
            )
        label = attachment.filename or attachment.mime_type
        return {"type": "text", "text": f"[附件：{label}]\n{attachment.extracted_text}"}

    if attachment.kind == "unknown":
        raise _attachment_error(f"无法识别 MIME 类型 {attachment.mime_type}")

    _require_capability(capabilities, attachment.kind)
    if not attachment.source_url:
        raise _attachment_error(f"{attachment.filename or attachment.mime_type} 缺少可访问内容")

    provider_key = f"{attachment.kind}_url"
    return {"type": provider_key, provider_key: {"url": attachment.source_url}}


def _normalize_provider_image_part(content: Mapping[str, object], role: object) -> dict[str, Any]:
    _require_user_attachment(role)
    image_url = content.get("image_url")
    if isinstance(image_url, str):
        image_url = {"url": image_url}
    if not isinstance(image_url, dict) or not isinstance(image_url.get("url"), str) or not image_url["url"]:
        raise _attachment_error("图片内容缺少 URL")
    return {"type": "image_url", "image_url": image_url}


def _normalize_provider_media_part(
    content: Mapping[str, object],
    *,
    role: object,
    capabilities: Mapping[str, bool],
    kind: str,
) -> dict[str, Any]:
    _require_user_attachment(role)
    _require_capability(capabilities, kind)
    provider_key = f"{kind}_url"
    media_url = content.get(provider_key)
    if isinstance(media_url, str):
        media_url = {"url": media_url}
    if not isinstance(media_url, dict) or not isinstance(media_url.get("url"), str) or not media_url["url"]:
        raise _attachment_error(f"{kind} 内容缺少 URL")
    return {"type": provider_key, provider_key: media_url}


def normalize_content_for_provider(
    content: list[object],
    *,
    role: object,
    capabilities: Mapping[str, bool] | None = None,
) -> list[dict[str, Any]]:
    """把消息内容映射为当前 provider 可接受的严格白名单。"""
    resolved_capabilities = {**_DEFAULT_CAPABILITIES, **dict(capabilities or {})}
    normalized: list[dict[str, Any]] = []

    for item in content:
        if isinstance(item, str):
            normalized.append({"type": "text", "text": item})
            continue
        if not isinstance(item, dict):
            raise AIDevException(message="不支持的消息内容：内容块必须是对象或文本")

        item_type = item.get("type")
        if item_type == "text":
            text = item.get("text")
            if not isinstance(text, str):
                raise AIDevException(message="不支持的消息内容：text 内容必须是字符串")
            normalized.append({"type": "text", "text": text})
        elif item_type == "image_url":
            _require_capability(resolved_capabilities, "image")
            normalized.append(_normalize_provider_image_part(item, role))
        elif item_type == "audio_url":
            normalized.append(
                _normalize_provider_media_part(
                    item,
                    role=role,
                    capabilities=resolved_capabilities,
                    kind="audio",
                )
            )
        elif item_type == "video_url":
            normalized.append(
                _normalize_provider_media_part(
                    item,
                    role=role,
                    capabilities=resolved_capabilities,
                    kind="video",
                )
            )
        elif item_type == "binary":
            normalized.append(
                _attachment_to_provider_part(
                    canonicalize_binary_attachment(item),
                    role=role,
                    capabilities=resolved_capabilities,
                )
            )
        else:
            raise AIDevException(message=f"不支持的消息内容类型：{item_type!r}")

    return normalized


def normalize_messages_for_provider(
    messages: list[object],
    *,
    capabilities: Mapping[str, bool] | None = None,
) -> list[dict[str, Any]]:
    """统一处理所有进入 provider 的消息，禁止原样透传非白名单 content part。"""
    normalized_messages: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise AIDevException(message="不支持的模型消息：消息必须是对象")

        normalized_message = dict(message)
        content = normalized_message.get("content")
        if isinstance(content, list):
            normalized_message["content"] = normalize_content_for_provider(
                content,
                role=normalized_message.get("role"),
                capabilities=capabilities,
            )
        normalized_messages.append(normalized_message)
    return normalized_messages
