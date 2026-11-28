import json

import pytest
from aidev_agent_adapter.services import adapter as adapter_module
from aidev_agent_adapter.services.config_sync import Snapshot
from aidev_agent_adapter.services.openclaw import install_user_config


def test_persistent_config_replacement_preserves_data_and_hides_headers(settings, tmp_path):
    user = tmp_path / "user"
    user.mkdir()
    state = user / "state"
    state.mkdir()
    (state / "memory.sqlite").write_bytes(b"test-state")
    source = tmp_path / "source"
    source.mkdir()
    config = {"mcp": {"servers": {"demo": {"headers": {"Authorization": "test-value"}}}}}
    (source / "openclaw.json").write_text(json.dumps(config))
    snapshot = Snapshot(source, "test", "openclaw")
    result = install_user_config(settings, snapshot, user)
    result = install_user_config(settings, result, user)
    assert result.environment["OPENCLAW_CONFIG_PATH"] == str(user / "openclaw.json")
    assert "test-value" not in (user / "openclaw.json").read_text()
    assert settings.engine_env["AIDEV_MCP_0_HEADER_0"] == "test-value"
    assert (state / "memory.sqlite").read_bytes() == b"test-state"


async def test_artifact_directories_separate_sessions(adapter, tmp_path, monkeypatch):
    adapter.settings.mounted_storage = True
    monkeypatch.setattr(adapter_module, "SESSION_VOLUME", tmp_path)
    first = adapter.session_directory("first")
    second = adapter.session_directory("second")
    (first / "output.txt").write_text("first only")
    assert not (second / "output.txt").exists()
    assert adapter.session_directory("first") == first
    for code in ("..", "/tmp/test", "one/two", ""):
        with pytest.raises(ValueError):
            adapter.session_directory(code)
    (tmp_path / "linked").symlink_to(first)
    with pytest.raises(ValueError):
        adapter.session_directory("linked")
