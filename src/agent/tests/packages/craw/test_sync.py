# -*- coding: utf-8 -*-
"""CrawSyncer：周期读写（health 打桩 + tmp_path 文件面）。"""

import json

import pytest

from aidev_agent.packages.craw import (
    CrawSyncer,
    OpenClawBackend,
    agent_config_to_artifacts,
    render_soul,
)


class _HealthStubBackend(OpenClawBackend):
    def __init__(self, ok=True):
        super().__init__(api_url="http://stub")
        self._ok = ok

    def health(self):
        return {"ok": self._ok, "status_code": 200 if self._ok else None, "latency_ms": 1.0, "backend": self.name}


class TestCrawSyncer:
    def test_run_cycle_writes_and_verifies_soul(self, tmp_path):
        syncer = CrawSyncer(
            backend=_HealthStubBackend(), home_dir=str(tmp_path), soul_provider=lambda: "# SOUL\nrole prompts"
        )
        result = syncer.run_cycle()
        assert result.ok and result.soul_verified
        assert (tmp_path / "SOUL.md").read_text(encoding="utf-8") == "# SOUL\nrole prompts"

    @pytest.mark.parametrize("ok, expected", [(True, True), (False, False)])
    def test_cycle_ok_follows_health(self, tmp_path, ok, expected):
        syncer = CrawSyncer(backend=_HealthStubBackend(ok=ok), home_dir=str(tmp_path))
        assert syncer.run_cycle().ok is expected

    def test_run_cycle_without_home_skips_file_side(self):
        syncer = CrawSyncer(backend=_HealthStubBackend(), soul_provider=lambda: "x")
        result = syncer.run_cycle()
        assert result.ok and result.soul_written_bytes == 0

    def test_run_forever_max_cycles(self, tmp_path):
        syncer = CrawSyncer(backend=_HealthStubBackend(), home_dir=str(tmp_path), interval=0.01)
        assert len(syncer.run_forever(max_cycles=2)) == 2

    def test_write_soul_without_home_raises(self):
        with pytest.raises(RuntimeError):
            CrawSyncer(backend=_HealthStubBackend()).write_soul("x")

    def test_artifacts_provider_writes_all_and_verifies(self, tmp_path):
        syncer = CrawSyncer(
            backend=_HealthStubBackend(),
            home_dir=str(tmp_path),
            artifacts_provider=lambda: {"SOUL.md": "# soul", "agent-config.json": '{"a":1}'},
        )
        result = syncer.run_cycle()
        assert result.ok and result.artifacts_verified
        assert set(result.artifacts_written) == {"SOUL.md", "agent-config.json"}
        assert (tmp_path / "agent-config.json").read_text(encoding="utf-8") == '{"a":1}'
        # 向后兼容别名仍指向 SOUL.md 一项
        assert result.soul_verified and result.soul_written_bytes == len("# soul".encode("utf-8"))

    def test_soul_and_artifacts_providers_merge(self, tmp_path):
        # soul_provider 的 SOUL.md 覆盖 artifacts_provider 的同名项
        syncer = CrawSyncer(
            backend=_HealthStubBackend(),
            home_dir=str(tmp_path),
            soul_provider=lambda: "# from-soul",
            artifacts_provider=lambda: {"SOUL.md": "# from-artifacts", "mcp.json": "{}"},
        )
        syncer.run_cycle()
        assert (tmp_path / "SOUL.md").read_text(encoding="utf-8") == "# from-soul"
        assert (tmp_path / "mcp.json").read_text(encoding="utf-8") == "{}"

    def test_write_artifact_nested_relpath(self, tmp_path):
        syncer = CrawSyncer(backend=_HealthStubBackend(), home_dir=str(tmp_path))
        syncer.write_artifact("skills/demo/SKILL.md", "hello")
        assert (tmp_path / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8") == "hello"


class TestPathEscapeRejected:
    """同步路径不得逃逸 craw home：绝对路径 / .. 跳转 / symlink escape 全部拒绝。"""

    @pytest.mark.parametrize("relpath", ["../evil.txt", "../../etc/passwd", "/abs/evil.txt"])
    def test_write_rejects_escape_relpath(self, tmp_path, relpath):
        syncer = CrawSyncer(backend=_HealthStubBackend(), home_dir=str(tmp_path))
        with pytest.raises(ValueError):
            syncer.write_artifact(relpath, "x")
        assert not (tmp_path.parent / "evil.txt").exists()

    @pytest.mark.parametrize("relpath", ["../evil.txt", "/abs/evil.txt"])
    def test_read_rejects_escape_relpath(self, tmp_path, relpath):
        syncer = CrawSyncer(backend=_HealthStubBackend(), home_dir=str(tmp_path))
        with pytest.raises(ValueError):
            syncer.read_file(relpath)

    def test_symlink_escape_rejected(self, tmp_path):
        outside = tmp_path.parent / f"{tmp_path.name}-outside"
        outside.mkdir()
        home = tmp_path / "home"
        home.mkdir()
        (home / "link").symlink_to(outside)
        syncer = CrawSyncer(backend=_HealthStubBackend(), home_dir=str(home))
        with pytest.raises(ValueError):
            syncer.write_artifact("link/evil.txt", "x")
        assert not (outside / "evil.txt").exists()

    def test_cycle_with_escape_relpath_enters_error_state(self, tmp_path):
        syncer = CrawSyncer(
            backend=_HealthStubBackend(),
            home_dir=str(tmp_path),
            artifacts_provider=lambda: {"../evil.txt": "x"},
        )
        result = syncer.run_cycle()
        assert not result.ok and result.error


class TestVerifyFailureMarksNotOk:
    """读回校验失败必须进入失败状态，不能把损坏配置当成功。"""

    def test_verify_failure_marks_result(self, tmp_path):
        syncer = CrawSyncer(backend=_HealthStubBackend(), home_dir=str(tmp_path), soul_provider=lambda: "# SOUL")
        # 模拟读回内容被篡改（与写入不一致）
        syncer.read_file = lambda relpath: "tampered"
        result = syncer.run_cycle()
        assert result.artifacts_verified is False
        assert result.artifacts_failed == ["SOUL.md"]
        assert result.ok is False
        assert "SOUL.md" in result.error


class TestAgentConfigToArtifacts:
    _CONFIG = {
        "agent_code": "demo-agent",
        "agent_name": "Demo",
        "chat_model": "demo-model",
        "role_prompts": [{"role": "system", "content": "你是 Demo。"}, {"role": "system", "content": "只说中文。"}],
        "mcp_server_config": {"bkm": {"url": "http://mcp"}},
        "related_skills": [{"code": "s1"}],
        "tool_codes": ["t1", "t2"],
    }

    def test_render_soul_joins_role_prompts(self):
        soul = render_soul(self._CONFIG)
        assert soul.startswith("# Demo")
        assert "你是 Demo。" in soul and "只说中文。" in soul

    def test_render_soul_fallback_without_prompts(self):
        assert render_soul({"agent_name": "Bare"}) == "# Bare\n"

    def test_artifacts_bundle_prompt_mcp_skills(self):
        arts = agent_config_to_artifacts(self._CONFIG)
        assert set(arts) == {"SOUL.md", "agent-config.json"}
        snap = json.loads(arts["agent-config.json"])
        assert snap["mcp_server_config"] == {"bkm": {"url": "http://mcp"}}
        assert snap["related_skills"] == [{"code": "s1"}]
        assert snap["tool_codes"] == ["t1", "t2"]

    def test_artifacts_feed_syncer_end_to_end(self, tmp_path):
        cfg = self._CONFIG
        syncer = CrawSyncer(
            backend=_HealthStubBackend(),
            home_dir=str(tmp_path),
            artifacts_provider=lambda: agent_config_to_artifacts(cfg),
        )
        result = syncer.run_cycle()
        assert result.ok and result.artifacts_verified
        assert (tmp_path / "SOUL.md").read_text(encoding="utf-8").startswith("# Demo")
        assert json.loads((tmp_path / "agent-config.json").read_text(encoding="utf-8"))["agent_code"] == "demo-agent"


class TestTwoPhaseTransaction:
    """产物集两阶段同步：任一产物 staging 失败 → 正式文件零改动。"""

    def test_second_artifact_failure_leaves_first_untouched(self, tmp_path):
        (tmp_path / "SOUL.md").write_text("# old-soul", encoding="utf-8")
        syncer = CrawSyncer(
            backend=_HealthStubBackend(),
            home_dir=str(tmp_path),
            # dict 有序：SOUL.md 先 staging 成功，第二个产物路径非法触发失败
            artifacts_provider=lambda: {"SOUL.md": "# new-soul", "../evil.txt": "x"},
        )
        result = syncer.run_cycle()
        assert not result.ok and result.error
        assert result.artifacts_written == {}  # 没有任何产物完成切换
        # 阶段一失败 → SOUL.md 正式文件保持旧版本，不出现"新 SOUL + 旧配置"混合态
        assert (tmp_path / "SOUL.md").read_text(encoding="utf-8") == "# old-soul"
        assert not (tmp_path.parent / "evil.txt").exists()

    def test_failed_cycle_leaves_no_staging_residue(self, tmp_path):
        syncer = CrawSyncer(
            backend=_HealthStubBackend(),
            home_dir=str(tmp_path),
            artifacts_provider=lambda: {"SOUL.md": "# soul", "bad/../../evil.txt": "x"},
        )
        syncer.run_cycle()
        residues = [p.name for p in tmp_path.rglob(".*craw-staging*")]
        assert residues == []

    def test_artifact_file_mode_0600(self, tmp_path):
        syncer = CrawSyncer(backend=_HealthStubBackend(), home_dir=str(tmp_path), soul_provider=lambda: "# soul")
        result = syncer.run_cycle()
        assert result.ok
        # 产物可能含 MCP 认证 header：不依赖 umask，显式 0600
        assert ((tmp_path / "SOUL.md").stat().st_mode & 0o777) == 0o600

    def test_symlink_final_target_replaced_not_followed(self, tmp_path):
        """正式文件名是指向 home 外的 symlink 时：rename 替换链接本身，外部文件不被写。"""
        outside = tmp_path.parent / f"{tmp_path.name}-outside-target"
        outside.write_text("outside-original", encoding="utf-8")
        home = tmp_path / "home"
        home.mkdir()
        (home / "SOUL.md").symlink_to(outside)
        syncer = CrawSyncer(backend=_HealthStubBackend(), home_dir=str(home))
        syncer.write_artifact("SOUL.md", "# new")
        assert outside.read_text(encoding="utf-8") == "outside-original"
        assert not (home / "SOUL.md").is_symlink()
        assert (home / "SOUL.md").read_text(encoding="utf-8") == "# new"


class TestCustomSoulFilename:
    """自定义 soul_filename 时，结果别名属性按实际文件名取数（不再硬编码 SOUL.md）。"""

    def test_result_aliases_follow_custom_filename(self, tmp_path):
        syncer = CrawSyncer(
            backend=_HealthStubBackend(),
            home_dir=str(tmp_path),
            soul_provider=lambda: "# persona",
            soul_filename="PERSONA.md",
        )
        result = syncer.run_cycle()
        assert result.ok
        assert result.soul_verified is True
        assert result.soul_written_bytes == len("# persona".encode("utf-8"))
        assert (tmp_path / "PERSONA.md").read_text(encoding="utf-8") == "# persona"
        assert not (tmp_path / "SOUL.md").exists()

    def test_artifact_mode_overridable_via_param_and_env(self, tmp_path, monkeypatch):
        """跨 UID 共享卷部署可放宽权限：参数 > env > 默认 0600。"""
        by_param = CrawSyncer(
            backend=_HealthStubBackend(), home_dir=str(tmp_path), soul_provider=lambda: "# a", artifact_mode=0o644
        )
        by_param.run_cycle()
        assert ((tmp_path / "SOUL.md").stat().st_mode & 0o777) == 0o644

        monkeypatch.setenv("BKAI_CRAW_ARTIFACT_MODE", "0640")
        by_env = CrawSyncer(
            backend=_HealthStubBackend(),
            home_dir=str(tmp_path),
            soul_provider=lambda: "# b",
            soul_filename="ENV.md",
        )
        by_env.run_cycle()
        assert ((tmp_path / "ENV.md").stat().st_mode & 0o777) == 0o640
