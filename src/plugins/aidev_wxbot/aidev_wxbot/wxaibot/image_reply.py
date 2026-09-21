"""企微机器人回复中的 Markdown 图片适配。"""

from __future__ import annotations

import base64
import hashlib
import io
import re
from dataclasses import dataclass
from logging import getLogger
from typing import Any, Callable
from urllib.parse import urlsplit

import requests
from aibot import generate_req_id
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

logger = getLogger(__name__)

MAX_IMAGE_ITEMS = 10
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
UPLOAD_CHUNK_BYTES = 512 * 1024
_MARKDOWN_IMAGE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<url>https?://[^\s)]+)\)")
_UPLOAD_INIT = "aibot_upload_media_init"
_UPLOAD_CHUNK = "aibot_upload_media_chunk"
_UPLOAD_FINISH = "aibot_upload_media_finish"


@dataclass(frozen=True, slots=True)
class PreparedImage:
    alt: str
    url: str
    data: bytes

    @property
    def md5(self) -> str:
        return hashlib.md5(self.data).hexdigest()


@dataclass(frozen=True, slots=True)
class PreparedCollageReply:
    markdown: str
    image: bytes
    image_count: int


def prepare_callback_image_reply(content: str) -> tuple[str, list[dict]]:
    """将 Markdown 图片转换为回调模式终帧支持的 ``msg_item``。"""
    prepared_content, images = _prepare_images(content)
    return prepared_content, build_image_msg_items(images)


def build_image_msg_items(images: list[PreparedImage]) -> list[dict]:
    return [
        {"msgtype": "image", "image": {"base64": base64.b64encode(image.data).decode("ascii"), "md5": image.md5}}
        for image in images
    ]


def render_long_connection_stream_content(content: str, *, finish: bool) -> str:
    """流式中间帧使用稳定占位符，终帧由拼图流程统一处理。"""
    return content if finish else _replace_with_placeholders(content)


def prepare_long_connection_collage(
    content: str, question: str, convert_urls: Callable[[list[str]], list[str]]
) -> PreparedCollageReply | None:
    """下载知识图片并构造原位占位 Markdown 和唯一拼图。"""
    all_matches = list(_MARKDOWN_IMAGE.finditer(content))
    matches = all_matches[:MAX_IMAGE_ITEMS]
    if not all_matches:
        return None
    converted_urls = convert_urls([match.group("url") for match in matches])
    if len(converted_urls) != len(matches):
        raise ValueError("知识库图片链接转换结果数量不一致")

    images: list[PreparedImage] = []
    replacements: dict[tuple[int, int], str] = {}
    for match in all_matches[MAX_IMAGE_ITEMS:]:
        replacements[match.span()] = _fallback_link(match.group("alt").strip(), match.group("url"))
    for match, download_url in zip(matches, converted_urls):
        image = _download_image(match.group("alt").strip(), download_url)
        if image is None or not _is_supported_image(image.data):
            replacements[match.span()] = _fallback_link(match.group("alt").strip(), match.group("url"))
            continue
        images.append(image)
        placeholder = _placeholder(len(images))
        replacements[match.span()] = _placeholder_block(placeholder)

    if not images:
        return None
    markdown = _replace_matches(content, all_matches, replacements)
    collage = _build_collage(images)
    return PreparedCollageReply(markdown=markdown, image=_encode_collage(collage), image_count=len(images))


async def upload_collage(client: Any, data: bytes) -> str:
    """使用企微长连接三段上传协议上传唯一拼图。"""
    chunks = [data[offset : offset + UPLOAD_CHUNK_BYTES] for offset in range(0, len(data), UPLOAD_CHUNK_BYTES)]
    filename = "knowledge-images.png" if data.startswith(b"\x89PNG\r\n\x1a\n") else "knowledge-images.jpg"
    init = await client._ws_manager.send_reply(
        generate_req_id(_UPLOAD_INIT),
        {
            "type": "image",
            "filename": filename,
            "total_size": len(data),
            "total_chunks": len(chunks),
            "md5": hashlib.md5(data).hexdigest(),
        },
        _UPLOAD_INIT,
    )
    _require_success(init, "init")
    upload_id = str((init.get("body") or {}).get("upload_id") or "")
    if not upload_id:
        raise RuntimeError("企微图片上传初始化未返回 upload_id")
    for index, chunk in enumerate(chunks):
        ack = await client._ws_manager.send_reply(
            generate_req_id(_UPLOAD_CHUNK),
            {"upload_id": upload_id, "chunk_index": index, "base64_data": base64.b64encode(chunk).decode("ascii")},
            _UPLOAD_CHUNK,
        )
        _require_success(ack, f"chunk-{index}")
    finish = await client._ws_manager.send_reply(
        generate_req_id(_UPLOAD_FINISH), {"upload_id": upload_id}, _UPLOAD_FINISH
    )
    _require_success(finish, "finish")
    media_id = str((finish.get("body") or {}).get("media_id") or "")
    if not media_id:
        raise RuntimeError("企微图片上传完成未返回 media_id")
    return media_id


def _replace_with_placeholders(content: str) -> str:
    index = 0

    def replace(_: re.Match) -> str:
        nonlocal index
        index += 1
        return _placeholder_block(_placeholder(index))

    return _MARKDOWN_IMAGE.sub(replace, content)


def _replace_matches(content: str, matches: list[re.Match], replacements: dict[tuple[int, int], str]) -> str:
    parts: list[str] = []
    position = 0
    for match in matches:
        parts.extend((content[position : match.start()], replacements.get(match.span(), match.group(0))))
        position = match.end()
    parts.append(content[position:])
    return "".join(parts)


def _placeholder(index: int) -> str:
    return f"IMG-{index:02d}"


def _placeholder_block(placeholder: str) -> str:
    return f"> **图片占位符 [{placeholder}]**  \n> 对应回复末尾合成长图中的 **[{placeholder}]** 区域。"


def _prepare_images(content: str) -> tuple[str, list[PreparedImage]]:
    images: list[PreparedImage] = []

    def replace(match: re.Match) -> str:
        alt, url = match.group("alt").strip(), match.group("url")
        if len(images) >= MAX_IMAGE_ITEMS:
            return _fallback_link(alt, url)
        image = _download_image(alt, url)
        if image is None:
            return _fallback_link(alt, url)
        images.append(image)
        return ""

    return _MARKDOWN_IMAGE.sub(replace, content), images


def _fallback_link(alt: str, url: str) -> str:
    return f"[查看图片：{alt or '未命名'}]({url})"


def _download_image(alt: str, url: str) -> PreparedImage | None:
    try:
        with requests.get(url, stream=True, timeout=(3, 12), allow_redirects=True) as response:
            response.raise_for_status()
            if int(response.headers.get("Content-Length") or 0) > MAX_IMAGE_BYTES:
                raise ValueError("image_too_large")
            data = _read_limited(response)
        return PreparedImage(alt=alt, url=url, data=data)
    except (OSError, ValueError, requests.RequestException) as error:
        logger.warning(
            "event=wxbot_reply_image_skipped reason=%s url_host=%s", type(error).__name__, urlsplit(url).hostname
        )
        return None


def _is_supported_image(data: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(data)) as opened:
            opened.verify()
        with Image.open(io.BytesIO(data)) as opened:
            if opened.width * opened.height > MAX_IMAGE_PIXELS:
                return False
        return True
    except (OSError, ValueError):
        return False


def _read_limited(response: Any) -> bytes:
    data = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        data.extend(chunk)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("image_too_large")
    if not data:
        raise ValueError("empty_image")
    return bytes(data)


def _font(size: int) -> ImageFont.ImageFont:
    """拼图只绘制 ASCII 固定文案，使用 Pillow 自带默认字体避免运行环境字体依赖。"""
    return ImageFont.load_default(size=size)


def _open_image(item: PreparedImage) -> Image.Image:
    with Image.open(io.BytesIO(item.data)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGBA")
    background = Image.new("RGBA", image.size, "white")
    return Image.alpha_composite(background, image).convert("RGB")


def _build_collage(images: list[PreparedImage]) -> Image.Image:
    margin, hero_height, footer_height, gap = 34, 170, 76, 36
    padding, header_height = 24, 82
    rendered = [_open_image(item) for item in images]
    title_font, subtitle_font, card_font, badge_font, footer_font = (
        _font(40),
        _font(22),
        _font(29),
        _font(19),
        _font(18),
    )
    max_image_width = max(image.width for image in rendered)
    content_width = max_image_width + 2 * padding
    title_width = round(title_font.getlength("KNOWLEDGE IMAGES"))
    footer_width = round(footer_font.getlength("SOURCE: KNOWLEDGE BASE"))
    footer_width += round(footer_font.getlength("GENERATED BY AI")) + margin
    max_badge = f"{_placeholder(len(rendered))} | {len(rendered)}/{len(rendered)}"
    card_width = 82 + round(card_font.getlength(f"IMAGE {len(rendered):02d}"))
    card_width += round(badge_font.getlength(max_badge)) + 60
    width = max(
        content_width + 2 * margin,
        title_width + 2 * margin,
        footer_width + 2 * margin,
        card_width + 2 * margin,
    )
    heights = [header_height + image.height + 2 * padding for image in rendered]
    total_height = hero_height + margin + sum(heights) + gap * (len(images) - 1) + footer_height
    canvas = Image.new("RGB", (width, total_height), "#f4f6fa")
    hero = Image.new("RGB", (width, hero_height), "#3859eb")
    hero_draw = ImageDraw.Draw(hero)
    for x in range(width):
        hero_draw.line((x, 0, x, hero_height), fill=(82 - x * 38 // width, 80 + x * 25 // width, 232 + x * 7 // width))
    canvas.paste(hero, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 43), "KNOWLEDGE IMAGES", font=title_font, fill="white")
    draw.text((margin, 108), f"{len(images)} IMAGES", font=subtitle_font, fill="#e4e8ff")
    y = hero_height + margin
    for index, (image, card_height) in enumerate(zip(rendered, heights), start=1):
        box = (margin, y, width - margin, y + card_height)
        shadow = Image.new("RGBA", (width - 2 * margin, card_height + 20), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((0, 7, shadow.width - 1, card_height + 9), 20, fill=(43, 55, 76, 45))
        blurred = shadow.filter(ImageFilter.GaussianBlur(11))
        canvas.paste(blurred, (margin, y), blurred)
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(box, radius=20, fill="white")
        draw.ellipse((margin + 28, y + 21, margin + 70, y + 63), fill="#1769e8")
        draw.text((margin + 49, y + 42), str(index), font=badge_font, fill="white", anchor="mm")
        draw.text((margin + 82, y + 21), f"IMAGE {index:02d}", font=card_font, fill="#202631")
        badge = f"{_placeholder(index)} | {index}/{len(images)}"
        badge_width = round(badge_font.getlength(badge)) + 24
        draw.rounded_rectangle(
            (width - margin - badge_width - 18, y + 23, width - margin - 18, y + 57), 10, fill="#2d6ce7"
        )
        draw.text((width - margin - badge_width - 6, y + 28), badge, font=badge_font, fill="white")
        image_x, image_y = (width - image.width) // 2, y + header_height + padding
        canvas.paste(image, (image_x, image_y))
        draw.rounded_rectangle(
            (image_x - 1, image_y - 1, image_x + image.width, image_y + image.height), 7, outline="#dfe3eb", width=2
        )
        y += card_height + gap
    footer_y = total_height - footer_height
    draw.line((margin, footer_y + 4, width - margin, footer_y + 4), fill="#d9dde6")
    draw.text((margin, footer_y + 28), "SOURCE: KNOWLEDGE BASE", font=footer_font, fill="#7c8491")
    draw.text((width - margin, footer_y + 28), "GENERATED BY AI", font=footer_font, fill="#7c8491", anchor="ra")
    return canvas


def _encode_collage(collage: Image.Image) -> bytes:
    lossless = io.BytesIO()
    collage.save(lossless, "PNG", optimize=True)
    lossless_data = lossless.getvalue()
    if len(lossless_data) <= MAX_IMAGE_BYTES:
        logger.info(
            "event=wxbot_collage_encoded format=png width=%d height=%d bytes=%d",
            collage.width,
            collage.height,
            len(lossless_data),
        )
        return lossless_data

    best_data: bytes | None = None
    best_quality = 0
    low, high = 1, 95
    while low <= high:
        quality = (low + high) // 2
        output = io.BytesIO()
        collage.save(output, "JPEG", quality=quality, subsampling=0, optimize=True, progressive=True)
        encoded = output.getvalue()
        if len(encoded) <= MAX_IMAGE_BYTES:
            best_data = encoded
            best_quality = quality
            low = quality + 1
        else:
            high = quality - 1
    if best_data is not None:
        logger.info(
            "event=wxbot_collage_encoded format=jpeg width=%d height=%d quality=%d bytes=%d lossless_bytes=%d",
            collage.width,
            collage.height,
            best_quality,
            len(best_data),
            len(lossless_data),
        )
        return best_data
    raise ValueError("collage_too_large")


def _require_success(ack: dict[str, Any], stage: str) -> None:
    if ack.get("errcode") not in (None, 0, "0"):
        raise RuntimeError(f"企微图片上传失败: stage={stage}, errcode={ack.get('errcode')}")
