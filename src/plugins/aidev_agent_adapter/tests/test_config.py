import io
import json
import zipfile

import httpx
import pytest
import yaml
from aidev_agent_adapter.config_sync import ConfigSynchronizer, render_mcp, unpack_skill
from aidev_agent_adapter.platform import PlatformClient, PlatformError


@pytest.mark.parametrize("engine", ["openclaw", "hermes"])
async def test_platform_to_native_profile(settings, platform, engine):
    settings.engine = engine
    sync = ConfigSynchronizer(settings, platform)
    snapshot = await sync.sync()
    prompt_dir = snapshot.workspace if engine == "openclaw" else snapshot.path
    assert (prompt_dir / "SOUL.md").read_text() == "Be helpful"
    assert (prompt_dir / "skills/sample/SKILL.md").is_file()
    config = (
        json.loads((snapshot.path / "openclaw.json").read_text())
        if engine == "openclaw"
        else yaml.safe_load((snapshot.path / "config.yaml").read_text())
    )
    servers = config["mcp"]["servers"] if engine == "openclaw" else config["mcp_servers"]
    assert servers["docs"]["toolFilter" if engine == "openclaw" else "tools"]["include"] == ["search"]
    assert (settings.root / "current").resolve() == snapshot.path
    assert (await sync.sync()).revision == snapshot.revision
    await platform.close()


@pytest.mark.parametrize("change", ["version", "checksum", "permission", "identity", "prompt", "binding"])
async def test_failed_update_preserves_previous(settings, platform, api_data, change):
    sync = ConfigSynchronizer(settings, platform)
    previous = await sync.sync()
    if change == "version":
        api_data["skill"]["version"] = "other"
    elif change == "checksum":
        api_data["skill"]["file_md5"] = "bad"
    elif change == "permission":
        api_data["agent"]["allowed_access"] = False
    elif change == "identity":
        api_data["agent"]["agent_code"] = "other"
    elif change == "prompt":
        api_data["agent"]["prompt_setting"]["content"] = [{"role": "user", "content": "hi"}]
    else:
        settings.skill_ids = [999]
    with pytest.raises(PlatformError):
        await sync.sync()
    assert (settings.root / "current").resolve() == previous.path
    await platform.close()


@pytest.mark.parametrize("filename", ["../escape", "/escape", "pkg/../../escape", "pkg\\escape", "C:/escape"])
def test_archive_rejects_traversal(tmp_path, filename):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as package:
        package.writestr("SKILL.md", "test")
        package.writestr(filename, "bad")
    with pytest.raises(ValueError):
        unpack_skill(output.getvalue(), tmp_path / "skill", 10000)
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize("engine", ["openclaw", "hermes"])
def test_tool_filter_empty_disables_and_glob_rejected(engine):
    server = {"url": "https://mcp.example", "selected_tools": []}
    assert render_mcp({"test": server}, engine)["test"]["enabled"] is False
    server["selected_tools"] = ["read_*"]
    with pytest.raises(ValueError):
        render_mcp({"test": server}, engine)


@pytest.mark.parametrize("status", [302, 401, 500])
async def test_download_http_failure_no_auth(settings, api_data, status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, headers={"Location": "https://evil.example"})

    client = PlatformClient(settings, httpx.MockTransport(handler))
    with pytest.raises(PlatformError):
        await client.download(api_data["skill"])
    assert len(requests) == 1
    assert "X-Bkapi-Authorization" not in requests[0].headers
    await client.close()


async def test_mcp_token_only_to_allowlisted_destination(settings):
    client = PlatformClient(settings)
    server = {"url": "https://foreign.example/mcp", "credential_type": "blueapps"}
    with pytest.raises(PlatformError):
        client.prepare_mcp(server)
    settings.mcp_auth_origins = ["https://foreign.example"]
    headers = client.prepare_mcp(server)["headers"]
    assert json.loads(headers["X-Bkapi-Authorization"]) == {"access_token": "test-only-token"}
    assert headers["X-Bk-Tenant-Id"] == "tenant"
    assert "bk_app_secret" not in str(headers)
    await client.close()


async def test_removed_resources_do_not_survive_new_snapshot(settings, platform, api_data):
    sync = ConfigSynchronizer(settings, platform)
    old = await sync.sync()
    api_data["agent"]["related_skills"] = {"skills": []}
    api_data["agent"]["mcp_server_config"] = {"mcpServers": {}}
    new = await sync.sync()
    assert new.revision != old.revision
    assert not (new.workspace / "skills/sample").exists()
    assert json.loads((new.path / "openclaw.json").read_text())["mcp"]["servers"] == {}
    assert (old.workspace / "skills/sample").exists()  # active generation remains stable
    await platform.close()


async def test_modified_snapshot_not_reused(settings, platform):
    sync = ConfigSynchronizer(settings, platform)
    snapshot = await sync.sync()
    (snapshot.workspace / "SOUL.md").write_text("modified")
    with pytest.raises(ValueError, match="modified"):
        await sync.sync()
    await platform.close()


async def test_configuration_root_cannot_be_rebound(settings, platform):
    sync = ConfigSynchronizer(settings, platform)
    await sync.sync()
    changed = settings.model_copy(update={"agent_code": "another-agent"})
    with pytest.raises(ValueError, match="identity mismatch"):
        await ConfigSynchronizer(changed, platform).sync()
    await platform.close()


@pytest.mark.parametrize("issue", ["symlink", "duplicate", "size", "missing-root"])
def test_archive_rejects_unsafe_content(tmp_path, issue):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as package:
        if issue != "missing-root":
            package.writestr("SKILL.md", "skill")
        if issue == "symlink":
            entry = zipfile.ZipInfo("escape")
            entry.external_attr = 0o120777 << 16
            package.writestr(entry, "../outside")
        elif issue == "duplicate":
            package.writestr("skill.MD", "duplicate")
        else:
            package.writestr("file.txt", "content")
    with pytest.raises(ValueError):
        unpack_skill(output.getvalue(), tmp_path / "skill", 1 if issue == "size" else 10000)


@pytest.mark.parametrize(
    "server",
    [
        {"url": "http://insecure.example"},
        {"url": "https://user:password@host.example"},
        {"command": "sh", "args": ["-c", "untrusted"]},
    ],
)
def test_unsupported_mcp_rejected(server):
    with pytest.raises((ValueError, PlatformError)):
        render_mcp({"server": server}, "openclaw")
