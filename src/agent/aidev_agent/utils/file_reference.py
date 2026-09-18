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
    只给路径，由模型自行调用 read_image 识别。

    连路径都没有时不提 read_image：没有 path 可传，模型照着提示也调不出结果，只会去猜一个
    不存在的路径。这种情况下如实说明取不到图，比给一个用不了的工具名更有用。
    """
    if not path:
        return "用户上传了一张图片，但当前取不到图片路径，无法识别图片内容。"
    return f"用户上传了图片：{path}，需要了解图片内容时调用 read_image 工具识别。"
