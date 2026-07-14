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
