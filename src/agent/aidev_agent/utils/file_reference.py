# -*- coding: utf-8 -*-
"""会话文件在模型输入里的引用契约。

刻意不 import 任何 aidev_agent 内部模块：模型输入组装（``core.nodes.model``）、网关请求
改写（``packages.langchain_core``）和 PV 文件服务（``services``）分属三层，共用同一份契约
只能放在没有依赖的叶子模块，否则各层只能各抄一份，文案和取值规则迟早分叉。
"""


def session_file_identity(item: dict) -> str:
    """解析会话文件身份：新契约 ``outputId``（上传 ``path``），其次 ``path``，最后旧 ``id``。"""
    raw = item.get("outputId") or item.get("path") or item.get("id")
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def image_content_url(item: dict) -> str:
    """读取图片内容 URL，兼容顶层 ``url`` 与标准 ``image_url.url``。"""
    if not isinstance(item, dict):
        return ""
    if item.get("type") == "image_url":
        image_url = item.get("image_url")
        raw = image_url.get("url") if isinstance(image_url, dict) else ""
    else:
        raw = item.get("url")
    return raw.strip() if isinstance(raw, str) else ""


def set_image_content_url(item: dict, url: str) -> None:
    """写回图片内容 URL，保持原有内容形态。"""
    if item.get("type") == "image_url":
        image_url = item.get("image_url")
        if isinstance(image_url, dict):
            image_url["url"] = url
        else:
            item["image_url"] = {"url": url}
    else:
        item["url"] = url


def clear_image_content_url(item: dict) -> None:
    """清除图片内容 URL，保持原有内容形态。"""
    if item.get("type") == "image_url":
        image_url = item.get("image_url")
        if isinstance(image_url, dict):
            image_url.pop("url", None)
    else:
        item.pop("url", None)


def image_session_file_path(item: dict) -> str:
    """读取图片对应的会话文件路径；网络 URL 不推断为当前会话文件。"""
    raw = session_file_identity(item)
    if not raw or raw.startswith(("http://", "https://")):
        return ""
    return raw


def is_image_content_item(item: dict) -> bool:
    """判断展示用 binary 是否为图片。

    判据与网关 ``ChatModel._get_request_payload`` 必须完全一致：装配链决定哪些图片降级，
    网关决定哪些 binary 能 materialize 成 image_url，两处对"什么算图片"的认定一旦分叉，
    就会出现装配链放过、网关又丢掉的静默失图。
    """
    return str(item.get("mime_type") or "").startswith("image/")


def image_reference_text(path: str) -> str:
    """图片不进模型输入时的替代文本。

    两种情况会用到：主模型不支持多模态，以及图片当下取不到 url / base64 data（重签失败）。
    给出 ``read_image`` 要求的 URI 形态；运行时名称由模型从工具描述的可选值中选择。

    连路径都没有时不提 read_image：没有 path 可传，模型照着提示也调不出结果，只会去猜一个
    不存在的路径。这种情况下如实说明取不到图，比给一个用不了的工具名更有用。
    """
    if not path:
        return "用户上传了一张图片，但当前取不到图片路径，无法识别图片内容。"
    image_path = path.strip("/")
    if not image_path.startswith(("$STORAGE_PATH/", "${STORAGE_PATH}/")):
        image_path = f"$STORAGE_PATH/session/{image_path}"
    return (
        f"用户上传了图片：file://<target_runtime>/{image_path}，"
        "需要了解图片内容时调用 read_image；请将 <target_runtime> 替换为工具提供的运行时名称。"
    )
