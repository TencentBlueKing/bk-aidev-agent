"""企微 Markdown 图片在回调和长连接模式下的协议适配测试。"""

from __future__ import annotations

import base64
import hashlib
import io
from types import SimpleNamespace

import pytest
from PIL import Image

from aidev_wxbot.wxaibot import image_reply
from aidev_wxbot.wxaibot.image_reply import (
    PreparedImage,
    build_image_msg_items,
    prepare_callback_image_reply,
    prepare_long_connection_collage,
    render_long_connection_stream_content,
    upload_collage,
)


def _png(color: str = "red", size: tuple[int, int] = (8, 6)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, "PNG")
    return output.getvalue()


def _prepared(alt: str, url: str, *, color: str = "red") -> PreparedImage:
    return PreparedImage(alt=alt, url=url, data=_png(color))


def test_callback_reply_removes_valid_images_and_builds_base64_items(monkeypatch):
    image = _prepared("架构图", "https://example.com/architecture.png")
    monkeypatch.setattr(image_reply, "_download_image", lambda alt, url: image)

    content, items = prepare_callback_image_reply("开始\n![架构图](https://example.com/architecture.png)\n结束")

    assert content == "开始\n\n结束"
    assert items == build_image_msg_items([image])
    assert base64.b64decode(items[0]["image"]["base64"]) == image.data
    assert items[0]["image"]["md5"] == hashlib.md5(image.data).hexdigest()


@pytest.mark.parametrize("downloaded", [None, PreparedImage("伪图片", "https://example.com/a.png", b"<html>")])
def test_callback_reply_keeps_fallback_link_for_unusable_image(monkeypatch, downloaded):
    monkeypatch.setattr(image_reply, "_download_image", lambda _alt, _url: downloaded)

    content, items = prepare_callback_image_reply("![伪图片](https://example.com/a.png)")

    assert content == "[查看图片：伪图片](https://example.com/a.png)"
    assert items == []


def test_callback_reply_caps_image_items_and_leaves_excess_as_links(monkeypatch):
    monkeypatch.setattr(image_reply, "MAX_IMAGE_ITEMS", 2)
    monkeypatch.setattr(image_reply, "_download_image", lambda alt, url: _prepared(alt, url))
    content = " ".join(f"![图{i}](https://example.com/{i}.png)" for i in range(3))

    rendered, items = prepare_callback_image_reply(content)

    assert len(items) == 2
    assert "[查看图片：图2](https://example.com/2.png)" in rendered


def test_intermediate_long_connection_frame_uses_stable_placeholders():
    content = "前文 ![图一](https://example.com/1.png) 后文 ![](http://example.com/2.jpg)"

    rendered = render_long_connection_stream_content(content, finish=False)

    assert "![" not in rendered
    assert "[IMG-01]" in rendered
    assert "[IMG-02]" in rendered
    assert render_long_connection_stream_content(content, finish=True) == content


def test_long_connection_collage_converts_urls_and_falls_back_per_invalid_image(monkeypatch):
    original_urls = ["https://knowledge.example.com/1.png", "https://knowledge.example.com/2.png"]
    converted_urls = ["https://download.example.com/1", "https://download.example.com/2"]
    captured_urls = []

    def convert(urls):
        captured_urls.extend(urls)
        return converted_urls

    def download(alt, url):
        if url.endswith("/2"):
            return PreparedImage(alt, url, b"not-an-image")
        return _prepared(alt, url)

    monkeypatch.setattr(image_reply, "_download_image", download)
    content = f"结果 ![图一]({original_urls[0]}) 以及 ![图二]({original_urls[1]})"

    prepared = prepare_long_connection_collage(content, "问题", convert)

    assert prepared is not None
    assert captured_urls == original_urls
    assert prepared.image_count == 1
    assert "[IMG-01]" in prepared.markdown
    assert f"[查看图片：图二]({original_urls[1]})" in prepared.markdown
    assert image_reply._is_supported_image(prepared.image)


def test_long_connection_collage_returns_none_without_markdown_images():
    def convert(_urls):
        pytest.fail("无图片时不应调用 URL 转换")

    assert prepare_long_connection_collage("纯文本", "问题", convert) is None


def test_long_connection_collage_rejects_mismatched_conversion_result():
    with pytest.raises(ValueError, match="数量不一致"):
        prepare_long_connection_collage("![图](https://example.com/a.png)", "问题", lambda _urls: [])


class _UploadManager:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    async def send_reply(self, request_id, body, command):
        self.calls.append((request_id, body, command))
        return next(self.replies)


async def test_upload_collage_uses_init_chunk_finish_protocol(monkeypatch):
    monkeypatch.setattr(image_reply, "UPLOAD_CHUNK_BYTES", 4)
    manager = _UploadManager(
        [
            {"errcode": 0, "body": {"upload_id": "upload-1"}},
            {"errcode": 0},
            {"errcode": 0},
            {"errcode": 0},
            {"errcode": 0, "body": {"media_id": "media-1"}},
        ]
    )
    data = b"abcdefghij"

    media_id = await upload_collage(SimpleNamespace(_ws_manager=manager), data)

    assert media_id == "media-1"
    assert [call[2] for call in manager.calls] == [
        "aibot_upload_media_init",
        "aibot_upload_media_chunk",
        "aibot_upload_media_chunk",
        "aibot_upload_media_chunk",
        "aibot_upload_media_finish",
    ]
    init_body = manager.calls[0][1]
    assert init_body["total_size"] == len(data)
    assert init_body["total_chunks"] == 3
    assert init_body["md5"] == hashlib.md5(data).hexdigest()
    assert [base64.b64decode(call[1]["base64_data"]) for call in manager.calls[1:4]] == [
        b"abcd",
        b"efgh",
        b"ij",
    ]


@pytest.mark.parametrize(
    ("replies", "message"),
    [
        ([{"errcode": 40001}], "stage=init"),
        ([{"errcode": 0, "body": {}}], "upload_id"),
        (
            [{"errcode": 0, "body": {"upload_id": "u"}}, {"errcode": 45009}],
            "stage=chunk-0",
        ),
        (
            [
                {"errcode": 0, "body": {"upload_id": "u"}},
                {"errcode": 0},
                {"errcode": 0, "body": {}},
            ],
            "media_id",
        ),
    ],
)
async def test_upload_collage_reports_protocol_failures(replies, message):
    manager = _UploadManager(replies)
    with pytest.raises(RuntimeError, match=message):
        await upload_collage(SimpleNamespace(_ws_manager=manager), b"image")


def test_download_image_enforces_streamed_size_limit(monkeypatch):
    class Response:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            assert chunk_size > 0
            yield b"1234"
            yield b"5678"

    monkeypatch.setattr(image_reply, "MAX_IMAGE_BYTES", 6)
    monkeypatch.setattr(image_reply.requests, "get", lambda *_args, **_kwargs: Response())

    assert image_reply._download_image("图", "https://example.com/a.png") is None
