# -*- coding: utf-8 -*-

from unittest.mock import Mock

import pytest
from aidev_agent.core.tools.skill.bkai_backend import BkAiBackend
from aidev_agent.core.tools.skill.types import SkillOptions

# ---------------------------------------------------------------------------
# 共用的 mock 数据
# ---------------------------------------------------------------------------

SKILL_MARKDOWN_WITH_FRONTMATTER = (
    "---\n"
    "name: pdf-create\n"
    "description: Use this skill to create PDFs\n"
    "license: Proprietary\n"
    "---\n\n"
    "# PDF Create Skill\n\n## Usage\nUse this skill to create PDF files..."
)

SKILL_MARKDOWN_RICH = (
    "---\n"
    "name: my-skill\n"
    "description: Full description\n"
    "license: MIT\n"
    "compatibility: v2.0+\n"
    "allowed-tools:\n"
    "  - bash\n"
    "  - python\n"
    "runtime: sandbox\n"
    "---\n\n"
    "# My Skill\n\nInstructions here."
)


SAMPLE_SANDBOX = {
    "image": "",
    "resources": {"requests": {"cpu": "1.0", "memory": "1.0"}},
    "envs": {"ACCESS_TOKEN": None, "WORKSPACE": "/app", "STORAGE_PATH": "/app/.storage/"},
}


@pytest.fixture
def mock_client():
    """Mock BK-AIDev client"""
    client = Mock()
    client.retrieve_skill = Mock(
        return_value={
            "id": "6",
            "version": "0.0.1",
            "name": "pdf-create",
            "skill_markdown": SKILL_MARKDOWN_WITH_FRONTMATTER,
            "sandbox": SAMPLE_SANDBOX,
        }
    )
    return client


@pytest.fixture
def mock_client_rich():
    """Mock client returning rich frontmatter"""
    client = Mock()
    client.retrieve_skill = Mock(
        return_value={
            "id": "1",
            "version": "1.0",
            "skill_markdown": SKILL_MARKDOWN_RICH,
            "sandbox": SAMPLE_SANDBOX,
        }
    )
    return client


@pytest.fixture
def related_skills():
    """Sample related_skills data"""
    return [
        {
            "id": 6,
            "skill_name": "pdf-create",
            "skill_code": "pdf_create",
            "description": "aaa",
            "skill_description": "Use this skill to create PDF files from various formats.",
            "version": "0.0.1",
            "latest_version": "0.0.1",
            "icon": "https://example.com/pdf.png",
            "is_public": True,
        },
        {
            "id": 7,
            "skill_name": "text-processor",
            "skill_code": "text_processor",
            "description": "Text processing",
            "skill_description": "Process and analyze text content.",
            "version": "1.0.0",
        },
    ]


class TestBkAiBackend:
    """Test suite for BkAiBackend"""

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def test_init(self, mock_client, related_skills):
        """Test initialization builds skill_options and calls API for each skill"""
        provider = BkAiBackend(mock_client, related_skills)

        assert provider.client is mock_client
        assert provider.related_skills == related_skills
        assert len(provider.skill_options) == 2
        # __init__ -> _build_skill_options -> convert_to_options -> _get_skill_data
        # 每个 skill 对应一次 API 调用
        assert mock_client.retrieve_skill.call_count == 2

    def test_repr(self, mock_client, related_skills):
        """Test __repr__"""
        provider = BkAiBackend(mock_client, related_skills)
        assert "BkAiBackend" in repr(provider)
        assert "skills=2" in repr(provider)

    # ------------------------------------------------------------------
    # discover()
    # ------------------------------------------------------------------

    def test_discover_returns_all_skills(self, mock_client, related_skills):
        """Test discover() returns all skills"""
        provider = BkAiBackend(mock_client, related_skills)
        skills = provider.discover()

        assert len(skills) == 2
        assert skills[0]["name"] == "pdf-create"
        assert skills[1]["name"] == "text-processor"

    def test_discover_skips_invalid_skills(self, mock_client):
        """Test discover() skips skills missing required fields"""
        invalid_skills = [
            {
                "id": 1,
                # 缺少 skill_name
                "skill_description": "Invalid skill",
                "version": "1.0",
            },
            {
                "id": 2,
                "skill_name": "valid-skill",
                "skill_description": "A valid skill",
                "version": "1.0",
            },
        ]
        provider = BkAiBackend(mock_client, invalid_skills)
        skills = provider.discover()

        assert len(skills) == 1
        assert skills[0]["name"] == "valid-skill"

    def test_discover_returns_same_reference(self, mock_client, related_skills):
        """Test discover() returns same list every time (initialized once)"""
        provider = BkAiBackend(mock_client, related_skills)
        skills1 = provider.discover()
        skills2 = provider.discover()

        assert skills1 is skills2

    def test_discover_metadata_structure(self, mock_client, related_skills):
        """Test discover() returns correct metadata structure (no internal fields)"""
        provider = BkAiBackend(mock_client, related_skills)
        skills = provider.discover()
        skill = skills[0]

        # Required fields
        assert "name" in skill
        assert "description" in skill
        assert "path" in skill
        assert skill["path"] == "api://6/0.0.1"

        # Internal fields should NOT exist
        assert "_api_id" not in skill
        assert "_api_version" not in skill
        assert "_skill_code" not in skill

        # Should NOT have instructions yet
        assert "instructions" not in skill

    def test_discover_uses_skill_description(self, mock_client, related_skills):
        """Test discover() uses skill_description over description"""
        provider = BkAiBackend(mock_client, related_skills)
        skills = provider.discover()
        skill = skills[0]

        assert "Use this skill to create PDF files from various formats." in skill["description"]
        assert skill["description"] != "aaa"

    def test_discover_optional_fields_from_frontmatter(self, mock_client):
        """Test discover() populates optional fields from API frontmatter"""
        mock_client.retrieve_skill.return_value = {
            "skill_markdown": SKILL_MARKDOWN_RICH,
        }
        related_skills = [
            {"id": 1, "skill_name": "my-skill", "skill_description": "Test", "version": "1.0"},
        ]
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]

        # Optional fields should already be set from frontmatter at discover time
        assert skill.get("license") == "MIT"
        assert skill.get("compatibility") == "v2.0+"
        assert skill.get("allowed_tools") == ["bash", "python"]
        assert skill.get("runtime") == "sandbox"

    def test_discover_no_optional_fields_when_no_frontmatter(self, mock_client):
        """Test discover() omits optional fields when frontmatter has none"""
        mock_client.retrieve_skill.return_value = {
            "skill_markdown": "# Just Instructions\n\nNo frontmatter here.",
        }
        related_skills = [
            {"id": 1, "skill_name": "plain-skill", "skill_description": "Plain", "version": "1.0"},
        ]
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]

        assert "license" not in skill
        assert "compatibility" not in skill
        assert "allowed_tools" not in skill
        # runtime defaults to "paas_sandbox" when frontmatter doesn't provide it
        assert skill["runtime"] == "paas_sandbox"

    # ------------------------------------------------------------------
    # _get_skill_data()
    # ------------------------------------------------------------------

    def test_get_skill_data_parses_api_response(self, mock_client):
        """Test _get_skill_data returns complete API response with parsed fields"""
        provider = BkAiBackend(mock_client, [])

        data = provider._get_skill_data("6", "0.0.1")

        assert "_cache_instructions" in data
        assert "_cache_frontmatter" in data
        assert "PDF Create Skill" in data["_cache_instructions"]
        assert data["_cache_frontmatter"].get("license") == "Proprietary"

    def test_get_skill_data_refetches_same_skill_version_for_env_changes(self, mock_client):
        """Test same skill_id/version is refetched because skill envs may change the API response"""
        provider = BkAiBackend(mock_client, [])
        mock_client.retrieve_skill.side_effect = [
            {
                "skill_markdown": "# First\n\nInstructions.",
                "sandbox": {"envs": {"SKILL_ENV": "first"}},
            },
            {
                "skill_markdown": "# Second\n\nInstructions.",
                "sandbox": {"envs": {"SKILL_ENV": "second"}},
            },
        ]

        first = provider._get_skill_data("6", "0.0.1")
        second = provider._get_skill_data("6", "0.0.1")

        assert first["sandbox"]["envs"]["SKILL_ENV"] == "first"
        assert second["sandbox"]["envs"]["SKILL_ENV"] == "second"
        assert mock_client.retrieve_skill.call_count == 2

    def test_get_skill_data_empty_markdown(self, mock_client):
        """Test _get_skill_data handles empty skill_markdown"""
        mock_client.retrieve_skill.return_value = {"id": "1", "version": "1.0"}
        provider = BkAiBackend(mock_client, [])

        data = provider._get_skill_data("1", "1.0")

        assert data["_cache_instructions"] == ""
        assert data["_cache_frontmatter"] == {}

    # ------------------------------------------------------------------
    # fetch_instructions()
    # ------------------------------------------------------------------

    def test_fetch_instructions_returns_body(self, mock_client, related_skills):
        """Test fetch_instructions() returns instructions from API response"""
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]

        instructions = provider.fetch_instructions(skill)
        assert "PDF Create Skill" in instructions
        assert "---" not in instructions

    def test_fetch_instructions_refetches_latest_data(self, mock_client):
        """Test fetch_instructions() triggers a fresh API call for the same skill_id/version"""
        mock_client.retrieve_skill.side_effect = [
            {"skill_markdown": "# Initial\n\nOld instructions."},
            {"skill_markdown": "# Latest\n\nNew instructions."},
        ]
        related_skills = [
            {"id": 1, "skill_name": "env-skill", "skill_description": "Test", "version": "1.0"},
        ]
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]

        instructions = provider.fetch_instructions(skill)

        assert "Latest" in instructions
        assert mock_client.retrieve_skill.call_count == 2

    def test_fetch_instructions_invalid_path(self, mock_client):
        """Test fetch_instructions() handles invalid path format"""
        provider = BkAiBackend(mock_client, [])
        skill: SkillOptions = {
            "name": "test",
            "description": "Test",
            "path": "invalid-path",
        }
        assert provider.fetch_instructions(skill) == ""
        mock_client.retrieve_skill.assert_not_called()

    def test_fetch_instructions_handles_api_error(self, mock_client):
        """Test fetch_instructions() handles API errors gracefully"""
        mock_client.retrieve_skill.side_effect = Exception("API error")

        related_skills = [
            {"id": 99, "skill_name": "fail-skill", "skill_description": "Fail", "version": "1.0"},
        ]
        # _convert_to_metadata will catch the exception and skip optional fields
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]

        # fetch_instructions calls _get_skill_data which will raise
        instructions = provider.fetch_instructions(skill)
        assert instructions == ""

    def test_fetch_instructions_no_frontmatter(self, mock_client):
        """Test fetch_instructions() works when skill_markdown has no frontmatter"""
        mock_client.retrieve_skill.return_value = {
            "skill_markdown": "# Just Instructions\n\nNo frontmatter here.",
        }
        related_skills = [
            {"id": 1, "skill_name": "plain", "skill_description": "Test", "version": "1.0"},
        ]
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]
        instructions = provider.fetch_instructions(skill)

        assert "Just Instructions" in instructions

    # ------------------------------------------------------------------
    # _parse_path()
    # ------------------------------------------------------------------

    def test_parse_path_valid(self):
        """Test _parse_path with valid api:// path"""
        assert BkAiBackend._parse_path("api://6/0.0.1") == ("6", "0.0.1")
        assert BkAiBackend._parse_path("api://123/latest") == ("123", "latest")

    def test_parse_path_invalid(self):
        """Test _parse_path with invalid paths"""
        assert BkAiBackend._parse_path("") == ("", "")
        assert BkAiBackend._parse_path("invalid") == ("", "")
        assert BkAiBackend._parse_path("api://") == ("", "")

    # ------------------------------------------------------------------
    # 无类级别缓存
    # ------------------------------------------------------------------

    def test_no_class_level_cache_attribute(self):
        """Test BkAiBackend no longer exposes class-level skill cache"""
        assert not hasattr(BkAiBackend, "_bkai_skill_cache")

    def test_instances_do_not_share_cached_skill_data(self, mock_client, related_skills):
        """Test each BkAiBackend instance fetches skill data independently"""
        BkAiBackend(mock_client, related_skills)
        call_count_after_p1 = mock_client.retrieve_skill.call_count

        BkAiBackend(mock_client, related_skills)

        assert mock_client.retrieve_skill.call_count == call_count_after_p1 + len(related_skills)

    # ------------------------------------------------------------------
    # Protocol & Integration
    # ------------------------------------------------------------------

    def test_protocol_compliance(self, mock_client, related_skills):
        """Test that BkAiBackend implements SkillProviderBackend protocol"""
        from aidev_agent.core.tools.skill.types import SkillProviderBackend

        provider = BkAiBackend(mock_client, related_skills)
        assert hasattr(provider, "discover") and callable(provider.discover)
        assert hasattr(provider, "fetch_instructions") and callable(provider.fetch_instructions)
        assert isinstance(provider, SkillProviderBackend)

    def test_integration_with_skill_registry(self, mock_client, related_skills):
        """Test integration with SkillRegistry"""
        from aidev_agent.core.tools.skill.provider import SkillRegistry

        provider = BkAiBackend(mock_client, related_skills)
        registry = SkillRegistry([provider])

        skills = registry.list_skills()
        assert len(skills) == 2

        skill = registry.get_skill("pdf-create")
        assert skill is not None
        assert skill["name"] == "pdf-create"

        activated = registry.activate_skill("pdf-create")
        assert activated is not None
        assert "instructions" in activated
        assert len(activated["instructions"]) > 0

    # ------------------------------------------------------------------
    # runtime 默认值
    # ------------------------------------------------------------------

    def test_runtime_defaults_to_paas_when_no_frontmatter_runtime(self, mock_client):
        """Test that runtime defaults to 'paas' when frontmatter has no runtime field"""
        mock_client.retrieve_skill.return_value = {
            "skill_markdown": SKILL_MARKDOWN_WITH_FRONTMATTER,
        }
        related_skills = [
            {"id": 1, "skill_name": "no-runtime", "skill_description": "Test", "version": "1.0"},
        ]
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]

        assert skill["runtime"] == "paas_sandbox"

    def test_runtime_preserved_when_frontmatter_provides_runtime(self, mock_client):
        """Test that frontmatter runtime value is preserved (not overwritten by default)"""
        mock_client.retrieve_skill.return_value = {
            "skill_markdown": SKILL_MARKDOWN_RICH,
        }
        related_skills = [
            {"id": 1, "skill_name": "with-runtime", "skill_description": "Test", "version": "1.0"},
        ]
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]

        assert skill["runtime"] == "sandbox"

    # ------------------------------------------------------------------
    # 边界场景
    # ------------------------------------------------------------------

    def test_empty_related_skills(self, mock_client):
        """Test with empty related_skills"""
        provider = BkAiBackend(mock_client, [])
        assert len(provider.discover()) == 0

    def test_fallback_to_short_description(self, mock_client):
        """Test fallback to short description when skill_description is missing"""
        related_skills = [
            {
                "id": 1,
                "skill_name": "test-skill",
                "description": "Short description",
                "version": "1.0",
            }
        ]
        provider = BkAiBackend(mock_client, related_skills)
        skills = provider.discover()

        assert len(skills) == 1
        assert "Short description" in skills[0]["description"]

    def test_path_pseudo_format(self, mock_client, related_skills):
        """Test that path uses pseudo-API format"""
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]
        assert skill["path"] == "api://6/0.0.1"

    def test_callee_agent_code_passed_to_retrieve_skill(self, mock_client):
        """Test callee_agent_code is preserved and passed when fetching skill data"""
        related_skills = [
            {
                "id": 1,
                "skill_name": "env-skill",
                "skill_description": "Uses skill envs",
                "version": "1.0",
                "callee_agent_code": "agent_a",
            },
        ]
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]

        assert skill["callee_agent_code"] == "agent_a"
        mock_client.retrieve_skill.assert_any_call(skill_id="1", version="1.0", callee_agent_code="agent_a")

        provider.fetch_instructions(skill)
        assert mock_client.retrieve_skill.call_args.kwargs["callee_agent_code"] == "agent_a"

    # ------------------------------------------------------------------
    # sandbox → metadata["metadata"]["bkai_paas_sandbox"]
    # ------------------------------------------------------------------

    def test_sandbox_written_to_metadata(self, mock_client, related_skills):
        """Test sandbox from API response is written into metadata.metadata.bkai_paas_sandbox"""
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]

        assert "metadata" in skill
        assert "bkai_paas_sandbox" in skill["metadata"]
        assert skill["metadata"]["bkai_paas_sandbox"] == SAMPLE_SANDBOX

    def test_sandbox_missing_no_metadata_key(self, mock_client):
        """Test that when sandbox is absent, bkai_paas_sandbox is not set"""
        mock_client.retrieve_skill.return_value = {
            "skill_markdown": "# No sandbox\n\nJust instructions.",
        }
        related_skills = [
            {"id": 1, "skill_name": "no-sandbox", "skill_description": "Test", "version": "1.0"},
        ]
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]

        # metadata key should not exist (no frontmatter metadata, no sandbox)
        assert "bkai_paas_sandbox" not in skill.get("metadata", {})

    def test_sandbox_empty_dict_not_written(self, mock_client):
        """Test that empty sandbox dict is not written"""
        mock_client.retrieve_skill.return_value = {
            "skill_markdown": "# Empty sandbox\n\nInstructions.",
            "sandbox": {},
        }
        related_skills = [
            {"id": 1, "skill_name": "empty-sandbox", "skill_description": "Test", "version": "1.0"},
        ]
        provider = BkAiBackend(mock_client, related_skills)
        skill = provider.discover()[0]

        assert "bkai_paas_sandbox" not in skill.get("metadata", {})

    def test_sandbox_coexists_with_frontmatter_metadata(self, mock_client_rich):
        """Test sandbox is added alongside existing frontmatter metadata fields"""
        mock_client_rich.retrieve_skill.return_value["skill_markdown"] = (
            "---\n"
            "name: my-skill\n"
            "description: Full description\n"
            "metadata:\n"
            "  author: test-user\n"
            "---\n\n"
            "# My Skill\n\nInstructions here."
        )
        related_skills = [
            {"id": 1, "skill_name": "my-skill", "skill_description": "Test", "version": "1.0"},
        ]
        provider = BkAiBackend(mock_client_rich, related_skills)
        skill = provider.discover()[0]

        # Both frontmatter metadata and sandbox should coexist
        assert skill["metadata"]["author"] == "test-user"
        assert skill["metadata"]["bkai_paas_sandbox"] == SAMPLE_SANDBOX
