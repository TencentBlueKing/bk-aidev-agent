# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.graphs.react.skill_middleware import SkillsPromptMiddleware
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext
from aidev_agent.core.tools.runtime_tools import RuntimeBackendResolver, get_execute_tool
from aidev_agent.core.tools.runtime_tools.local_backend import FilesystemBackend
from aidev_agent.core.tools.skill import SkillOptions
from aidev_agent.core.tools.skill.provider import SkillRegistry
from aidev_agent.pydantic_models import AgentExecutorKwargs


def _write_skill(root: Path, *, name: str, description: str, body: str, runtime: str | None = None) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    frontmatter = f"name: {name}\ndescription: {description}\n"
    if runtime is not None:
        frontmatter += f"runtime: {runtime}\n"
    skill_md.write_text(
        "---\n" + frontmatter + "---\n\n" + body + "\n",
        encoding="utf-8",
    )
    return skill_md


class MockSkillProvider:
    """Minimal SkillProvider for testing register_provider behavior."""

    def __init__(self, skills: list[SkillOptions]) -> None:
        self._skills = skills

    def discover(self) -> list[SkillOptions]:
        return self._skills

    def fetch_instructions(self, skill: SkillOptions) -> str:
        return f"instructions for {skill['name']}"


class TestSkillRegistry:
    def test_registry_lazy_load_and_activate(self, tmp_path: Path):
        skills_root = tmp_path / "skills"
        _write_skill(skills_root, name="my-skill", description="desc", body="Do the thing")

        registry = SkillRegistry([str(skills_root)])
        assert registry._loaded is False

        skills = registry.list_skills()
        assert registry._loaded is True
        assert [s["name"] for s in skills] == ["my-skill"]

        summary = registry.get_skills_summary()
        assert "my-skill" in summary
        assert "desc" in summary

        activated = registry.activate_skill("my-skill")
        assert activated is not None
        assert "instructions" in activated
        assert "---" not in activated["instructions"]
        assert "Do the thing" in activated["instructions"]

    def test_register_provider_resets_loaded_flag(self, tmp_path: Path):
        """register_provider 必须将 _loaded 置为 False，确保新 provider 的技能能被发现。"""
        # 初始只有一个 provider，提供一个技能
        skills_root = tmp_path / "skills"
        _write_skill(skills_root, name="existing-skill", description="desc", body="Body")

        registry = SkillRegistry([str(skills_root)])

        # 触发加载
        skills_before = registry.list_skills()
        assert registry._loaded is True
        assert [s["name"] for s in skills_before] == ["existing-skill"]

        # 注册一个新 provider，提供另一个技能
        new_provider = MockSkillProvider(
            [
                {"name": "new-skill", "description": "new desc", "path": "/fake/path"},
            ]
        )
        registry.register_provider(new_provider)

        # _loaded 应被重置为 False
        assert registry._loaded is False

        # 下次访问应重新加载，包含两个 provider 的技能
        skills_after = registry.list_skills()
        assert registry._loaded is True
        skill_names = [s["name"] for s in skills_after]
        assert "existing-skill" in skill_names
        assert "new-skill" in skill_names

    def test_register_provider_before_load(self, tmp_path: Path):
        """register_provider 在首次加载前调用，仍应正常工作。"""
        registry = SkillRegistry([])
        assert registry._loaded is False

        new_provider = MockSkillProvider(
            [
                {"name": "only-skill", "description": "desc", "path": "/fake"},
            ]
        )
        registry.register_provider(new_provider)

        skills = registry.list_skills()
        assert registry._loaded is True
        assert [s["name"] for s in skills] == ["only-skill"]


class TestSkillOptionsRuntime:
    """Tests for runtime field in SkillOptions parsing."""

    def test_skill_with_runtime_field(self, tmp_path: Path):
        """Skill with runtime declared in frontmatter should have it in metadata."""
        skills_root = tmp_path / "skills"
        _write_skill(skills_root, name="remote-skill", description="desc", body="Body", runtime="sandbox")

        registry = SkillRegistry([str(skills_root)])
        skills = registry.list_skills()
        assert len(skills) == 1
        assert skills[0]["runtime"] == "sandbox"

    def test_skill_without_runtime_field(self, tmp_path: Path):
        """Skill without runtime declared should fall back to "local".

        ReActAgentBuilder._prepare_skills skips skills whose runtime is None, so
        LocalBackend defaults undeclared runtime to "local" to keep them usable.
        """
        skills_root = tmp_path / "skills"
        _write_skill(skills_root, name="local-skill", description="desc", body="Body")

        registry = SkillRegistry([str(skills_root)])
        skills = registry.list_skills()
        assert len(skills) == 1
        assert skills[0]["runtime"] == "local"

    def test_skill_runtime_local(self, tmp_path: Path):
        """Skill with runtime=local should have it in metadata."""
        skills_root = tmp_path / "skills"
        _write_skill(skills_root, name="explicit-local", description="desc", body="Body", runtime="local")

        registry = SkillRegistry([str(skills_root)])
        skills = registry.list_skills()
        assert len(skills) == 1
        assert skills[0]["runtime"] == "local"


class TestSkillRuntimeBackend:
    def test_execute_in_skill_scripts_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        skills_root = tmp_path / "skills"
        skill_md = _write_skill(skills_root, name="my-skill", description="desc", body="Body")
        scripts_dir = skill_md.parent / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "run.sh").write_text("echo skill-run-ok\n", encoding="utf-8")

        # 安全校验默认只允许 /workspace,/home,/tmp,/app 下的脚本，
        # 而 pytest 在 macOS 上的 tmp_path 实际是 /private/var/folders/...
        # 这里将 tmp_path 加入白名单，保证脚本能被允许执行。
        monkeypatch.setattr(
            "aidev_agent.core.tools.runtime_tools.security.DEFAULT_ALLOWED_SCRIPT_DIRS",
            [str(tmp_path)],
        )

        resolver = RuntimeBackendResolver(default_runtime="local")
        resolver.register_runtime("local", FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True))
        resolver.register_runtime(
            "local_my-skill",
            FilesystemBackend(root_dir=str(scripts_dir), virtual_mode=True),
        )

        execute_tool = get_execute_tool(resolver)
        script_path = str(scripts_dir / "run.sh")
        out = execute_tool.invoke({"command": f"bash {script_path}", "target_runtime": "local_my-skill"})
        assert "skill-run-ok" in out


class TestReActBuilderSkillsIntegration:
    def test_builder_injects_tools_and_middleware(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        # Arrange: make ./ .agent/skills available
        monkeypatch.chdir(tmp_path)
        skills_root = tmp_path / ".agent" / "skills"
        skill_md = _write_skill(skills_root, name="my-skill", description="desc", body="Do X", runtime="local")
        scripts_dir = skill_md.parent / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "run.sh").write_text("echo skill-run-ok\n", encoding="utf-8")

        # 同上：将 tmp_path 加入安全校验白名单
        monkeypatch.setattr(
            "aidev_agent.core.tools.runtime_tools.security.DEFAULT_ALLOWED_SCRIPT_DIRS",
            [str(tmp_path)],
        )

        llm = MagicMock()
        llm.model_name = "gpt-4o"

        captured = {}

        def _fake_make_model_node(*, llm, non_thinking_llm, judge_llm, tools, node_options):
            captured["tools"] = tools
            captured["node_options"] = node_options
            return MagicMock()

        with (
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", new=_fake_make_model_node),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            # P0 调序：resolver 注入（set_bkai_options）须先于 skills 链式 enable_runtime_local
            # （新方案 enable_runtime_* 要求 resolver 已存在）；真实 resolver 会让
            # enable_runtime_local 经 register_runtime_cls("local", FilesystemBackend) 注册
            builder = (
                ReActAgentBuilder()
                .set_llm(llm)
                .set_bkai_options(
                    AgentExecutorKwargs(
                        runtime_backend_resolver=RuntimeBackendResolver(),
                    )
                )
                .set_enable_skills(True)
                .set_enable_runtime_tool(True)
                .set_skill_sources([str(skills_root)])
                .enable_runtime_local(True)
            )
            builder.build()

        tools = captured["tools"]
        tool_names = {t.name for t in tools}
        assert "activate_skill" in tool_names
        assert "execute" in tool_names

        # activate_skill returns SKILL.md body (no frontmatter)
        activate_tool = next(t for t in tools if t.name == "activate_skill")
        activated = activate_tool.invoke({"skill_name": "my-skill"})
        assert "Do X" in activated
        assert "---" not in activated

        # execute can run scripts via per-skill runtime
        execute_tool = next(t for t in tools if t.name == "execute")
        script_path = str(scripts_dir / "run.sh")
        out = execute_tool.invoke({"command": f"bash {script_path}", "target_runtime": "local_my-skill"})
        assert "skill-run-ok" in out

        # middleware injection contains skills discovery summary
        node_options = captured["node_options"]
        middlewares = getattr(node_options, "extra_template_middlewares", [])
        sm = next(m for m in middlewares if isinstance(m, SkillsPromptMiddleware))

        ctx = ProcessorContext(state={"decision": "general"}, config={}, store=None)
        ctx.prompt_slots.system = "BASE"
        sm(ctx, lambda: None)
        assert "my-skill" in ctx.prompt_slots.system
