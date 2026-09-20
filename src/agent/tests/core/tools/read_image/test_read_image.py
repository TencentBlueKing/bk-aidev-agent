# -*- coding: utf-8 -*-
"""read_image 工具测试：schema / runtime 路由 / 取图 / 多模态 message / 返回结构。"""

import json
from tempfile import TemporaryDirectory
from typing import TypedDict
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.core.tools import read_image as read_image_module
from aidev_agent.core.tools.read_image import NO_VISION_OUTPUT_MESSAGE, make_read_image_tool
from aidev_agent.core.tools.runtime_tools.local_backend import FilesystemBackend
from aidev_agent.core.tools.runtime_tools.provider import RuntimeBackendResolver
from langchain_core.messages import AIMessage, ToolCall, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"


def _schema_properties(tool) -> dict:
    # pydantic v1: schema(); pydantic v2: model_json_schema()
    if getattr(tool, "args_schema", None) is None:
        return {}

    schema = None
    if hasattr(tool.args_schema, "schema"):
        schema = tool.args_schema.schema()  # type: ignore[attr-defined]
    elif hasattr(tool.args_schema, "model_json_schema"):
        schema = tool.args_schema.model_json_schema()  # type: ignore[attr-defined]

    if not isinstance(schema, dict):
        return {}
    return schema.get("properties", {}) or {}


def _mock_resolver(backend) -> MagicMock:
    """构造 resolver mock：resolve_backend 返回指定后端，描述方法返回纯文本。"""
    resolver = MagicMock()
    resolver.resolve_backend.return_value = backend
    resolver.runtime_param_description.return_value = "运行此工具的目标运行时（必填）。可选值: local。"
    return resolver


class TestReadImageSchema:
    """IMG-01：工具 schema 与描述。"""

    def test_schema_exposes_model_visible_params(self, resolver, vision_llm):
        tool = make_read_image_tool(resolver, vision_llm)
        props = _schema_properties(tool)

        assert tool.name == "read_image"
        assert "image_uri" in props
        assert "prompt" in props
        assert "target_runtime" not in props
        assert "image_path" not in props
        assert "config" not in props

    def test_default_description_non_empty(self, resolver, vision_llm):
        tool = make_read_image_tool(resolver, vision_llm)
        assert tool.description.strip()

    def test_custom_description_overrides(self, resolver, vision_llm):
        tool = make_read_image_tool(resolver, vision_llm, custom_description="自定义")
        assert tool.description == "自定义"


class TestReadImageRuntimeRouting:
    """IMG-02：runtime 路由与动态描述。"""

    def test_runtime_param_description_lists_registered_names(self, vision_llm):
        with TemporaryDirectory() as d1, TemporaryDirectory() as d2:
            resolver = RuntimeBackendResolver(default_runtime="local")
            resolver.register_runtime("local", FilesystemBackend(root_dir=d1))
            resolver.register_runtime("sandbox_1", FilesystemBackend(root_dir=d2))

            props = _schema_properties(make_read_image_tool(resolver, vision_llm))
            runtime_desc = props["image_uri"].get("description", "")
            assert "local" in runtime_desc
            assert "sandbox_1" in runtime_desc
            assert "file://" in runtime_desc

    def test_unknown_runtime_raises_with_available_list(self, resolver, vision_llm):
        tool = make_read_image_tool(resolver, vision_llm)
        with pytest.raises(ValueError, match="Available runtimes:"):
            tool.invoke({"image_uri": "file://nope/shot.png", "prompt": "这是什么"})

    def test_registered_runtime_resolves_to_backend(self, resolver, vision_llm, tmp_path, to_image_uri):
        (tmp_path / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-png-body")
        tool = make_read_image_tool(resolver, vision_llm)
        result = tool.invoke({"image_uri": to_image_uri(str(tmp_path / "shot.png")), "prompt": "这是什么"})
        assert json.loads(result)["summary"] == "报错截图"


class TestReadImageDownload:
    """IMG-03：取图、编码与多模态 message 形态。"""

    @pytest.mark.parametrize(
        "error, expected_fragment",
        [
            ("file_not_found", "图片不存在"),
            ("permission_denied", "无权限"),
            ("is_directory", "目录"),
            ("invalid_path", "路径非法"),
        ],
    )
    def test_download_error_messages(self, error, expected_fragment, vision_llm):
        backend = MagicMock()
        backend.download_files.return_value = [{"path": "/x.png", "content": None, "error": error}]
        tool = make_read_image_tool(_mock_resolver(backend), vision_llm)
        with pytest.raises(ValueError, match=expected_fragment):
            tool.invoke({"image_uri": "file://local/x.png", "prompt": "p"})

    def test_empty_responses_raises(self, vision_llm):
        backend = MagicMock()
        backend.download_files.return_value = []
        tool = make_read_image_tool(_mock_resolver(backend), vision_llm)
        with pytest.raises(ValueError, match="未返回任何结果"):
            tool.invoke({"image_uri": "file://local/x.png", "prompt": "p"})

    def test_missing_download_files_raises(self, vision_llm):
        tool = make_read_image_tool(_mock_resolver(object()), vision_llm)
        with pytest.raises(ValueError, match="不支持图片下载"):
            tool.invoke({"image_uri": "file://local/x.png", "prompt": "p"})

    def test_unsupported_suffix_raises(self, resolver, vision_llm, tmp_path, to_image_uri):
        (tmp_path / "shot.bmp").write_bytes(b"bmp")
        tool = make_read_image_tool(resolver, vision_llm)
        with pytest.raises(ValueError, match="不支持的图片格式"):
            tool.invoke({"image_uri": to_image_uri(str(tmp_path / "shot.bmp")), "prompt": "p"})

    @pytest.mark.parametrize(
        "filename, expected_prefix",
        [
            ("a.png", "data:image/png;base64,"),
            ("a.jpg", "data:image/jpeg;base64,"),
            ("a.jpeg", "data:image/jpeg;base64,"),
            ("a.gif", "data:image/gif;base64,"),
            ("a.webp", "data:image/webp;base64,"),
        ],
    )
    def test_base64_prefix_by_suffix(self, filename, expected_prefix, resolver, vision_llm, tmp_path, to_image_uri):
        (tmp_path / filename).write_bytes(b"img")
        tool = make_read_image_tool(resolver, vision_llm)
        tool.invoke({"image_uri": to_image_uri(str(tmp_path / filename)), "prompt": "p"})

        content = vision_llm.invoke.call_args.args[0][0].content
        assert content[0]["image_url"]["url"].startswith(expected_prefix)

    def test_multimodal_message_shape(self, resolver, vision_llm, tmp_path, to_image_uri):
        (tmp_path / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-png-body")
        tool = make_read_image_tool(resolver, vision_llm)
        tool.invoke({"image_uri": to_image_uri(str(tmp_path / "shot.png")), "prompt": "这张图是什么"})

        content = vision_llm.invoke.call_args.args[0][0].content
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0]["type"] == "image_url"
        assert content[1] == {"type": "text", "text": "这张图是什么"}

    def test_oversized_image_raises(self, resolver, vision_llm, tmp_path, to_image_uri, monkeypatch):
        monkeypatch.setattr("aidev_agent.core.tools.read_image._MAX_IMAGE_BYTES", 1)
        (tmp_path / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-png-body")
        tool = make_read_image_tool(resolver, vision_llm)
        with pytest.raises(ValueError, match="图片过大"):
            tool.invoke({"image_uri": to_image_uri(str(tmp_path / "shot.png")), "prompt": "p"})


class TestReadImageReturnShape:
    """IMG-05：返回结构与兜底。"""

    @pytest.fixture
    def image_file(self, tmp_path, to_image_uri):
        """写入假 PNG 并返回其 image_uri。"""
        path = tmp_path / "shot.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-png-body")
        return to_image_uri(str(path))

    def test_json_return_shape(self, resolver, vision_llm, image_file):
        tool = make_read_image_tool(resolver, vision_llm)
        result = tool.invoke({"image_uri": image_file, "prompt": "p"})

        parsed = json.loads(result)
        assert set(parsed) == {"summary", "text"}
        assert isinstance(parsed["summary"], str)
        assert isinstance(parsed["text"], str)

    def test_ensure_ascii_false_preserves_chinese(self, resolver, vision_llm, image_file):
        tool = make_read_image_tool(resolver, vision_llm)
        result = tool.invoke({"image_uri": image_file, "prompt": "p"})

        assert "报错截图" in result
        assert "\\u" not in result

    def test_non_json_fallback(self, resolver, vision_llm, image_file):
        vision_llm.invoke.return_value = AIMessage(content="这是一张报错截图")
        tool = make_read_image_tool(resolver, vision_llm)
        result = tool.invoke({"image_uri": image_file, "prompt": "p"})

        assert json.loads(result) == {"summary": "", "text": "这是一张报错截图"}

    def test_message_content_parts_list(self, resolver, vision_llm, image_file):
        vision_llm.invoke.return_value = AIMessage(content=[{"type": "text", "text": "部分文本"}])
        tool = make_read_image_tool(resolver, vision_llm)
        result = tool.invoke({"image_uri": image_file, "prompt": "p"})

        assert json.loads(result)["text"] == "部分文本"

    @pytest.mark.parametrize("content", ["", "   ", []])
    def test_empty_vision_output_yields_signal(self, resolver, vision_llm, image_file, content):
        """视觉模型无输出时不返回静默空结果，而是留可观测提示。"""
        vision_llm.invoke.return_value = AIMessage(content=content)
        tool = make_read_image_tool(resolver, vision_llm)
        result = tool.invoke({"image_uri": image_file, "prompt": "p"})

        parsed = json.loads(result)
        assert parsed["summary"] == ""
        assert parsed["text"] == NO_VISION_OUTPUT_MESSAGE

    def test_none_vision_output_yields_signal(self, resolver, vision_llm, image_file):
        """模型直接返回 None（非 AIMessage）时同样留提示，不静默空结果。"""
        vision_llm.invoke.return_value = None
        tool = make_read_image_tool(resolver, vision_llm)
        result = tool.invoke({"image_uri": image_file, "prompt": "p"})

        assert json.loads(result)["text"] == NO_VISION_OUTPUT_MESSAGE

    @pytest.mark.parametrize("content", ['["a", "b"]', "123", '"裸字符串"'])
    def test_non_object_json_preserves_raw_text(self, resolver, vision_llm, image_file, content):
        """合法但非对象的 JSON 不丢信息：原文完整保留在 text。"""
        vision_llm.invoke.return_value = AIMessage(content=content)
        tool = make_read_image_tool(resolver, vision_llm)
        result = tool.invoke({"image_uri": image_file, "prompt": "p"})

        parsed = json.loads(result)
        assert parsed["summary"] == ""
        assert parsed["text"] == content

    def test_oversize_image_raises(self, resolver, vision_llm, tmp_path, to_image_uri, monkeypatch):
        """超过体积上限的图片被拒绝，不进入编码与模型调用。"""
        monkeypatch.setattr(read_image_module, "_MAX_IMAGE_BYTES", 1)
        (tmp_path / "big.png").write_bytes(b"x" * 64)
        tool = make_read_image_tool(resolver, vision_llm)

        with pytest.raises(ValueError, match="图片过大"):
            tool.invoke({"image_uri": to_image_uri(str(tmp_path / "big.png")), "prompt": "p"})
        vision_llm.invoke.assert_not_called()

    def test_download_error_message_is_passed_through_verbatim(self, vision_llm):
        """下载错误文案原样返回给模型，不做额外改写。"""
        backend = MagicMock()
        backend.download_files.return_value = [{"path": "/x.png", "content": None, "error": "file_not_found"}]
        tool = make_read_image_tool(_mock_resolver(backend), vision_llm)
        with pytest.raises(ValueError, match="图片不存在，请确认路径：/x.png"):
            tool.invoke({"image_uri": "file://local/x.png", "prompt": "p"})

    def test_download_receives_injected_state(self, vision_llm, tmp_path, to_image_uri):
        """state 必须透传给后端 download_files（PaaS 首次建沙箱靠它挂 PV）。"""
        backend = MagicMock()
        backend.download_files.return_value = [{"path": "/x.png", "content": PNG_BYTES, "error": None}]
        tool = make_read_image_tool(_mock_resolver(backend), vision_llm)

        tool.invoke(
            {"image_uri": to_image_uri(str(tmp_path / "shot.png")), "prompt": "p"},
            config={"configurable": {"thread_id": "t-1"}},
        )

        _, kwargs = backend.download_files.call_args
        assert "state" in kwargs


class TestReadImageFrontEndDisplay:
    """视觉模型调用期间关闭前端显示与落库，异常路径也必须恢复。"""

    @patch("aidev_agent.core.tools.read_image.conditional_dispatch_custom_event")
    def test_dispatch_false_then_true_around_invoke(self, mock_dispatch, resolver, vision_llm, tmp_path, to_image_uri):
        """invoke 前派发 False，invoke 后派发 True。"""
        (tmp_path / "shot.png").write_bytes(PNG_BYTES)
        tool = make_read_image_tool(resolver, vision_llm)
        tool.invoke({"image_uri": to_image_uri(str(tmp_path / "shot.png")), "prompt": "p"})

        assert mock_dispatch.call_count == 2
        assert mock_dispatch.call_args_list[0].args == ("custom_event", {"front_end_display": False})
        assert mock_dispatch.call_args_list[1].args == ("custom_event", {"front_end_display": True})

    @patch("aidev_agent.core.tools.read_image.conditional_dispatch_custom_event")
    def test_dispatch_true_restored_on_vision_failure(
        self, mock_dispatch, resolver, vision_llm, tmp_path, to_image_uri
    ):
        """视觉模型抛异常时 finally 仍恢复 True（否则后续输出被永久抑制）。"""
        vision_llm.invoke.side_effect = RuntimeError("vision timeout")
        (tmp_path / "shot.png").write_bytes(PNG_BYTES)
        tool = make_read_image_tool(resolver, vision_llm)

        with pytest.raises(RuntimeError, match="vision timeout"):
            tool.invoke({"image_uri": to_image_uri(str(tmp_path / "shot.png")), "prompt": "p"})

        assert mock_dispatch.call_count == 2
        assert mock_dispatch.call_args_list[0].args == ("custom_event", {"front_end_display": False})
        assert mock_dispatch.call_args_list[-1].args == ("custom_event", {"front_end_display": True})


class TestReadImageUriParsing:
    """image_uri 解析规则与边界。"""

    @pytest.mark.parametrize(
        "uri",
        [
            "/abs/shot.png",  # 无 file:// 前缀
            "local/shot.png",  # 无 file:// 前缀
            "http://local/shot.png",  # 非 file:// scheme
            "file:///shot.png",  # runtime 为空
            "file://local/",  # 路径为空
            "file://local",  # 缺分割斜杠
            "",  # 空串
        ],
    )
    def test_invalid_uri_raises(self, uri, resolver, vision_llm):
        """无 file:// 前缀 / 缺 runtime / 缺路径 一律报错，不回退默认 runtime。"""
        tool = make_read_image_tool(resolver, vision_llm)
        with pytest.raises(ValueError, match="image_uri 格式非法"):
            tool.invoke({"image_uri": uri, "prompt": "p"})

    def test_missing_prefix_does_not_fall_back_to_default_runtime(self, resolver, vision_llm, tmp_path):
        """无前缀时不得静默走 default_runtime='local'。"""
        (tmp_path / "shot.png").write_bytes(PNG_BYTES)
        tool = make_read_image_tool(resolver, vision_llm)
        with pytest.raises(ValueError, match="image_uri 格式非法"):
            tool.invoke({"image_uri": str(tmp_path / "shot.png"), "prompt": "p"})

    @pytest.mark.parametrize("uri_runtime", ["local", "paas_sandbox_my-skill"])
    def test_runtime_name_with_separators_resolves(self, uri_runtime, resolver, vision_llm, tmp_path):
        """runtime 名可同时含 _ 与 -，首个 / 才是安全分割点。"""
        (tmp_path / "shot.png").write_bytes(PNG_BYTES)
        tool = make_read_image_tool(resolver, vision_llm)
        uri = f"file://{uri_runtime}{tmp_path}/shot.png"
        assert json.loads(tool.invoke({"image_uri": uri, "prompt": "p"}))["summary"] == "报错截图"

    def test_multi_level_path_preserved(self, resolver, vision_llm, tmp_path):
        """多级路径完整传给后端，不被首个 / 之后的额外斜杠截断。"""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        (nested / "shot.png").write_bytes(PNG_BYTES)
        tool = make_read_image_tool(resolver, vision_llm)
        uri = f"file://local{tmp_path}/a/b/c/shot.png"
        assert json.loads(tool.invoke({"image_uri": uri, "prompt": "p"}))["summary"] == "报错截图"

    def test_unknown_runtime_in_uri_raises(self, resolver, vision_llm):
        """URI 语法合法但 runtime 未注册时报错并列出可选值。"""
        tool = make_read_image_tool(resolver, vision_llm)
        with pytest.raises(ValueError, match="Available runtimes:"):
            tool.invoke({"image_uri": "file://not_registered/shot.png", "prompt": "p"})

    @pytest.mark.parametrize(
        "uri, expected_path",
        [
            ("file://paas_sandbox/x/$STORAGE_PATH/session/upload/shot.png", "/x/$STORAGE_PATH/session/upload/shot.png"),
            ("file://paas_sandbox/x/${STORAGE_PATH}/a/b.png", "/x/${STORAGE_PATH}/a/b.png"),
            ("file://paas_sandbox/x/$STORAGE_PATH", "/x/$STORAGE_PATH"),
            ("file://local/shot.png", "/shot.png"),
            ("file://local/a/b/c.png", "/a/b/c.png"),
            ("file://local/abs/shot.png", "/abs/shot.png"),
            ("file://local/$STORAGE_PATHX/a.png", "/$STORAGE_PATHX/a.png"),
            ("file://local/$STORAGE_PATH", "$STORAGE_PATH"),
        ],
    )
    def test_storage_path_prefix_preserved(self, uri, expected_path):
        """$STORAGE_PATH 字面量不被补前导 /（否则后端展开分支失配）。"""
        _, path = read_image_module._parse_image_uri(uri)
        assert path == expected_path


class InjectionTestState(TypedDict):
    """测试用图状态。"""

    messages: list


class InjectionStateWithPV(TypedDict):
    """测试用图状态：含 PV 信息键以验证 state 注入内容。"""

    messages: list
    runtime_paas_sbx_pv: list


class TestReadImageToolNodeInjection:
    """集成层：验证 RunnableConfig 注入不破。"""

    def test_read_image_config_injection_via_tool_node(self, resolver, vision_llm, tmp_path, to_image_uri):
        (tmp_path / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-png-body")
        tool = make_read_image_tool(resolver, vision_llm)

        workflow = StateGraph(InjectionTestState)
        workflow.add_node("tools", ToolNode([tool]))
        workflow.add_edge(START, "tools")
        workflow.add_edge("tools", END)
        graph = workflow.compile()

        ai_message = AIMessage(
            content="",
            tool_calls=[
                ToolCall(
                    name="read_image",
                    args={"image_uri": to_image_uri(str(tmp_path / "shot.png")), "prompt": "p"},
                    id="call_001",
                    type="tool_call",
                )
            ],
        )
        result = graph.invoke({"messages": [ai_message]}, config={"configurable": {"thread_id": "t-456"}})

        tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_messages) == 1
        assert json.loads(tool_messages[0].content)["summary"]

    def test_read_image_state_injection_via_tool_node(self, vision_llm, tmp_path, to_image_uri):
        """ToolNode 调用期 state 真的填进 download_files。"""
        seen = {}

        class SpyBackend:
            def download_files(self, paths, *, state=None):
                seen["state"] = state
                return [{"path": paths[0], "content": PNG_BYTES, "error": None}]

        tool = make_read_image_tool(_mock_resolver(SpyBackend()), vision_llm)
        workflow = StateGraph(InjectionStateWithPV)
        workflow.add_node("tools", ToolNode([tool]))
        workflow.add_edge(START, "tools")
        workflow.add_edge("tools", END)
        graph = workflow.compile()

        ai_message = AIMessage(
            content="",
            tool_calls=[
                ToolCall(
                    name="read_image",
                    args={"image_uri": to_image_uri(str(tmp_path / "shot.png")), "prompt": "p"},
                    id="call_003",
                    type="tool_call",
                )
            ],
        )
        graph.invoke(
            {
                "messages": [ai_message],
                "runtime_paas_sbx_pv": [{"type": "paas-sbx-pv", "volume_id": "v-1", "mount_path": "session"}],
            },
            config={"configurable": {"thread_id": "t-789"}},
        )

        assert seen["state"]["runtime_paas_sbx_pv"][0]["volume_id"] == "v-1"
