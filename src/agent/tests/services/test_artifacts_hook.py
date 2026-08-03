# -*- coding: utf-8 -*-
"""artifacts_generated 业务层 hook 契约测试（services/agent/artifacts.py）。

覆盖点：
- ``_has_session_pv`` 判定（true/false 各分支）
- ``_files_to_artifacts`` 转换（目录过滤 / 空 path 过滤 / name 兜底 / 后缀提取）
- ``build_artifacts_generated_hook`` 退化：无 PV / rm=None 均返回空 async generator
- 正常路径：hook emit CustomEvent 并调用 ``dispatch_event``
- 异常兜底：PaaS 抛错时 hook 静默 return，不 emit、不重抛
- BaseSessionWriter 分发路径（artifacts_generated → handle_artifacts_generated）保持不变

协议层（`_emit_run_end_extras` 转发行为、事件时序）测试见
``tests/core/ag_ui/test_run_end_extras_hook.py``。
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from ag_ui.core import CustomEvent, EventType
from aidev_agent.enums import ActivityType, PromptRole
from aidev_agent.services.agent.artifacts import (
    _files_to_artifacts,
    _has_session_pv,
    build_artifacts_generated_hook,
)
from aidev_agent.services.event_handlers.base import BaseSessionWriter


# ---------------------------------------------------------------------------
# _has_session_pv
# ---------------------------------------------------------------------------


class TestHasSessionPv:
    def test_session_pv_present(self):
        state = {
            "runtime_paas_sbx_pv": [
                {"type": "paas-sbx-pv", "mount_path": "session", "volume_id": "vol-1"},
            ]
        }
        assert _has_session_pv(state) is True

    def test_empty_state(self):
        assert _has_session_pv({}) is False

    def test_wrong_mount_path(self):
        state = {"runtime_paas_sbx_pv": [{"type": "paas-sbx-pv", "mount_path": "other", "volume_id": "v"}]}
        assert _has_session_pv(state) is False

    def test_no_volume_id(self):
        state = {"runtime_paas_sbx_pv": [{"type": "paas-sbx-pv", "mount_path": "session"}]}
        assert _has_session_pv(state) is False


# ---------------------------------------------------------------------------
# _files_to_artifacts
# ---------------------------------------------------------------------------


class TestFilesToArtifacts:
    def test_normal_conversion(self):
        files = [
            {"path": "outputs/report.pdf", "name": "report.pdf", "size": 2048, "is_dir": False},
        ]
        assert _files_to_artifacts(files) == [
            {"outputId": "outputs/report.pdf", "type": "pdf", "name": "report.pdf", "size": 2048},
        ]

    def test_filters_directories(self):
        files = [
            {"path": "outputs/", "is_dir": True},
            {"path": "outputs/a.txt", "name": "a.txt", "size": 10, "is_dir": False},
        ]
        result = _files_to_artifacts(files)
        assert len(result) == 1
        assert result[0]["outputId"] == "outputs/a.txt"

    def test_no_extension_type_is_file(self):
        files = [{"path": "outputs/README", "name": "README", "size": 5, "is_dir": False}]
        assert _files_to_artifacts(files)[0]["type"] == "file"

    def test_name_falls_back_to_basename(self):
        files = [{"path": "a/b/c.md", "size": 3, "is_dir": False}]
        result = _files_to_artifacts(files)
        assert result[0]["name"] == "c.md"
        assert result[0]["type"] == "md"

    def test_empty_path_skipped(self):
        files = [{"path": "", "name": "x", "size": 1, "is_dir": False}]
        assert _files_to_artifacts(files) == []

    def test_missing_size_defaults_to_zero(self):
        files = [{"path": "a.txt", "name": "a.txt", "is_dir": False}]
        assert _files_to_artifacts(files)[0]["size"] == 0


# ---------------------------------------------------------------------------
# build_artifacts_generated_hook —— 退化与正常/异常路径
# ---------------------------------------------------------------------------


def _consume(hook, state, thread_id, active_run=None, dispatch=None):
    """驱动 hook 拿到全部 yield 结果的辅助函数。"""
    import asyncio

    active_run = active_run if active_run is not None else {"id": "run-1", "started_at": None}
    dispatch = dispatch if dispatch is not None else (lambda ev: ev)

    async def _drive():
        return [
            ev
            async for ev in hook(
                state_values=state,
                thread_id=thread_id,
                active_run=active_run,
                dispatch_event=dispatch,
            )
        ]

    return asyncio.run(_drive())


class TestHookDegrade:
    """退化路径：无 PV / rm=None 时 hook 直接空 generator，不构造 SandboxPvFileService。"""

    def test_no_session_pv_returns_silently(self):
        hook = build_artifacts_generated_hook(resource_manager=MagicMock(), executor_info={})
        with patch("aidev_agent.services.agent.artifacts.SandboxPvFileService") as svc_cls:
            events = _consume(hook, {}, "sess-1")
        assert events == []
        svc_cls.assert_not_called()

    def test_no_resource_manager_returns_silently(self):
        hook = build_artifacts_generated_hook(resource_manager=None, executor_info={"app_code": "x"})
        state = {
            "runtime_paas_sbx_pv": [
                {"type": "paas-sbx-pv", "mount_path": "session", "volume_id": "v"},
            ]
        }
        with patch("aidev_agent.services.agent.artifacts.SandboxPvFileService") as svc_cls:
            events = _consume(hook, state, "sess-1")
        assert events == []
        svc_cls.assert_not_called()


class TestHookNormalPath:
    """正常路径：emit CustomEvent + 走 dispatch_event。"""

    _state = {
        "runtime_paas_sbx_pv": [
            {"type": "paas-sbx-pv", "mount_path": "session", "volume_id": "v"},
        ]
    }

    def test_success_emits_custom_event(self):
        hook = build_artifacts_generated_hook(resource_manager=MagicMock(), executor_info={})
        dispatch = MagicMock(side_effect=lambda ev: ev)
        with patch("aidev_agent.services.agent.artifacts.SandboxPvFileService") as svc_cls:
            svc_cls.return_value.list_files.return_value = {
                "results": [
                    {"path": "outputs/a.txt", "name": "a.txt", "size": 3, "is_dir": False},
                ]
            }
            events = _consume(hook, self._state, "sess-1", dispatch=dispatch)

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, CustomEvent)
        assert event.type == EventType.CUSTOM
        assert event.name == "artifacts_generated"
        assert event.value == {
            "runId": "run-1",
            "status": "complete",
            "artifacts": [
                {"outputId": "outputs/a.txt", "type": "txt", "name": "a.txt", "size": 3},
            ],
        }
        # dispatch_event 必须被调用一次（走 DB writer + SSE 分发通道）
        dispatch.assert_called_once()

    def test_empty_result_emits_empty_status(self):
        hook = build_artifacts_generated_hook(resource_manager=MagicMock(), executor_info={})
        with patch("aidev_agent.services.agent.artifacts.SandboxPvFileService") as svc_cls:
            svc_cls.return_value.list_files.return_value = {"results": []}
            events = _consume(hook, self._state, "sess-1")

        assert len(events) == 1
        assert events[0].value["status"] == "empty"
        assert events[0].value["artifacts"] == []

    def test_active_run_started_at_forwarded_to_list_files(self):
        """active_run.started_at 应作为 since 传给 list_files。"""
        hook = build_artifacts_generated_hook(resource_manager=MagicMock(), executor_info={})
        sentinel = object()
        with patch("aidev_agent.services.agent.artifacts.SandboxPvFileService") as svc_cls:
            svc_cls.return_value.list_files.return_value = {"results": []}
            _consume(
                hook,
                self._state,
                "sess-9",
                active_run={"id": "run-9", "started_at": sentinel},
            )
        svc_cls.return_value.list_files.assert_called_once_with(
            session_code="sess-9", since=sentinel
        )


class TestHookExceptionSwallowed:
    """异常兜底：PaaS 抛错 → hook 静默 return，不 emit、不重抛。"""

    _state = {
        "runtime_paas_sbx_pv": [
            {"type": "paas-sbx-pv", "mount_path": "session", "volume_id": "v"},
        ]
    }

    def test_paas_failure_swallowed(self):
        hook = build_artifacts_generated_hook(resource_manager=MagicMock(), executor_info={})
        dispatch = MagicMock()
        with patch("aidev_agent.services.agent.artifacts.SandboxPvFileService") as svc_cls:
            svc_cls.return_value.list_files.side_effect = RuntimeError("paas down")
            events = _consume(hook, self._state, "sess-1", dispatch=dispatch)
        assert events == []
        dispatch.assert_not_called()


# ---------------------------------------------------------------------------
# 保留：BaseSessionWriter 白名单分发 + handle_artifacts_generated 落库路径
# ---------------------------------------------------------------------------


class TestBaseSessionWriterArtifactsGenerated:
    """白名单分发 + handle_artifacts_generated 默认钩子返回 False 时兜底走 _create_session_content。"""

    def _make_writer(self) -> BaseSessionWriter:
        class _W(BaseSessionWriter):
            def _do_create_content(self, message_id, action, payload, headers):
                return 123

            def _do_update_content(self, content_id, payload, headers):
                pass

        writer = _W.__new__(_W)
        writer.session_code = "sess-1"
        writer.username = "u"
        writer.turn_id = ""
        writer._written_message_ids = set()
        writer._streaming_messages = {}
        writer._content_ids_by_message_id = {}
        writer._is_cancelled = False
        writer._has_run_error = False
        return writer

    def test_activity_type_added(self):
        assert ActivityType.ARTIFACTS_GENERATED.value == "artifacts_generated"

    def test_dispatch_routes_to_handler(self):
        writer = self._make_writer()
        with patch.object(writer, "handle_artifacts_generated") as h:
            writer._dispatch_custom_event_direct(
                CustomEvent(type=EventType.CUSTOM, name="artifacts_generated", value={})
            )
            h.assert_called_once()

    def test_handle_creates_session_content(self):
        writer = self._make_writer()
        event = CustomEvent(
            type=EventType.CUSTOM,
            name="artifacts_generated",
            value={"runId": "run-1", "status": "complete", "artifacts": [{"outputId": "a.txt"}]},
        )
        with patch.object(writer, "_create_session_content") as mocked:
            writer.handle_artifacts_generated(event)
            mocked.assert_called_once()
            kwargs = mocked.call_args.kwargs
            assert kwargs["role"] == PromptRole.ACTIVITY.value
            assert kwargs["status"] == "success"
            assert kwargs["builtin_property"]["type"] == "artifacts_generated"
            assert kwargs["builtin_property"]["run_id"] == "run-1"
            assert json.loads(kwargs["content"]) == event.value

    def test_dedup_by_message_id(self):
        writer = self._make_writer()
        event = CustomEvent(
            type=EventType.CUSTOM,
            name="artifacts_generated",
            value={"runId": "run-1", "artifacts": []},
        )
        with patch.object(writer, "_create_session_content") as mocked:
            writer.handle_artifacts_generated(event)
            writer.handle_artifacts_generated(event)
            assert mocked.call_count == 1

# ---------------------------------------------------------------------------
# 新行为: 合并进最近一条 assistant 消息的 property.artifacts + 无 assistant 兜底
# ---------------------------------------------------------------------------


class TestPickLastAssistant:
    """_pick_last_assistant 纯函数: 内存选出 id 最大的 assistant 记录。"""

    def test_picks_max_id_assistant(self):
        contents = [
            {"id": 1, "role": "user"},
            {"id": 2, "role": "assistant"},
            {"id": 5, "role": "assistant"},
            {"id": 6, "role": "tool"},
        ]
        assert BaseSessionWriter._pick_last_assistant(contents)["id"] == 5

    def test_returns_none_without_assistant(self):
        contents = [{"id": 1, "role": "user"}, {"id": 2, "role": "tool"}]
        assert BaseSessionWriter._pick_last_assistant(contents) is None

    def test_supports_object_items(self):
        class _Row:
            def __init__(self, rid, role):
                self.id = rid
                self.role = role
        rows = [_Row(3, "assistant"), _Row(7, "assistant"), _Row(9, "user")]
        assert BaseSessionWriter._pick_last_assistant(rows).id == 7


class TestMergeArtifactsIntoProperty:
    """_merge_artifacts_into_property 纯函数: 顶层数组合并 + outputId 去重。"""

    def test_appends_to_empty(self):
        prop = {}
        out = BaseSessionWriter._merge_artifacts_into_property(prop, [{"outputId": "a"}])
        assert out["artifacts"] == [{"outputId": "a"}]

    def test_dedup_by_output_id(self):
        prop = {"artifacts": [{"outputId": "a", "name": "old"}]}
        out = BaseSessionWriter._merge_artifacts_into_property(
            prop, [{"outputId": "a", "name": "new"}, {"outputId": "b"}]
        )
        ids = [x["outputId"] for x in out["artifacts"]]
        assert ids == ["a", "b"]


class TestHandleArtifactsMergeBehavior:
    """handle_artifacts_generated 新落库行为: 优先合并, 失败兜底 activity。"""

    def _make_writer(self):
        class _W(BaseSessionWriter):
            def _do_create_content(self, message_id, action, payload, headers):
                return 123

            def _do_update_content(self, content_id, payload, headers):
                pass

        writer = _W.__new__(_W)
        writer.session_code = "sess-1"
        writer.username = "u"
        writer.turn_id = ""
        writer._written_message_ids = set()
        writer._streaming_messages = {}
        writer._content_ids_by_message_id = {}
        writer._is_cancelled = False
        writer._has_run_error = False
        return writer

    def _event(self):
        return CustomEvent(
            type=EventType.CUSTOM,
            name="artifacts_generated",
            value={"runId": "run-1", "status": "complete", "artifacts": [{"outputId": "a.txt"}]},
        )

    def test_merge_success_skips_activity(self):
        """合并成功(钩子返回 True)时不再建 activity。"""
        writer = self._make_writer()
        with patch.object(writer, "_merge_artifacts_into_last_assistant", return_value=True) as merge:
            with patch.object(writer, "_create_session_content") as create:
                writer.handle_artifacts_generated(self._event())
        merge.assert_called_once()
        create.assert_not_called()
        assert "artifacts_run-1" in writer._written_message_ids

    def test_merge_failure_falls_back_to_activity(self):
        """合并失败(钩子返回 False)时兜底建 activity。"""
        writer = self._make_writer()
        with patch.object(writer, "_merge_artifacts_into_last_assistant", return_value=False):
            with patch.object(writer, "_create_session_content") as create:
                writer.handle_artifacts_generated(self._event())
        create.assert_called_once()
        assert create.call_args.kwargs["role"] == PromptRole.ACTIVITY.value

    def test_no_artifacts_skips_merge_and_creates_activity(self):
        """无 artifacts 数组时不调用合并钩子, 直接走兜底 activity。"""
        writer = self._make_writer()
        event = CustomEvent(
            type=EventType.CUSTOM,
            name="artifacts_generated",
            value={"runId": "run-2", "status": "empty", "artifacts": []},
        )
        with patch.object(writer, "_merge_artifacts_into_last_assistant") as merge:
            with patch.object(writer, "_create_session_content") as create:
                writer.handle_artifacts_generated(event)
        merge.assert_not_called()
        create.assert_called_once()

    def test_default_hook_returns_false(self):
        """基类默认 _merge_artifacts_into_last_assistant 返回 False(保持旧行为)。"""
        writer = self._make_writer()
        assert writer._merge_artifacts_into_last_assistant([{"outputId": "a"}], {}) is False

