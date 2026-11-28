import asyncio
import hashlib
import io
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from aidev_agent_adapter.adapter import Adapter
from aidev_agent_adapter.config_sync import ConfigSynchronizer
from aidev_agent_adapter.models import Settings
from aidev_agent_adapter.platform import PlatformClient


@pytest.fixture
def settings(tmp_path):
    return Settings(
        endpoint="https://platform.example",
        agent_code="agent",
        agent_app_code="app",
        tenant_id="tenant",
        access_token="test-only-token",
        version="1.0.0",
        engine="openclaw",
        root=tmp_path / "instance",
    )


@pytest.fixture
def archive():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as package:
        package.writestr("sample/SKILL.md", "---\nname: sample\ndescription: test\n---\nInstruction")
        package.writestr("sample/scripts/helper.py", "print('ok')")
    return output.getvalue()


@pytest.fixture
def api_data(archive):
    return {
        "agent": {
            "agent_code": "app",
            "allowed_access": True,
            "prompt_setting": {"content": [{"role": "system", "content": "Be helpful"}]},
            "mcp_server_config": {
                "mcpServers": {
                    "docs": {
                        "url": "https://mcp.example/mcp",
                        "transport": "streamable_http",
                        "selected_tools": ["search"],
                    }
                }
            },
            "related_skills": {"skills": [{"id": 1, "version": "2.0"}]},
        },
        "skill": {
            "id": 1,
            "version": "2.0",
            "skill_code": "sample",
            "url": "https://platform.example/pkg.zip",
            "file_md5": hashlib.md5(archive, usedforsecurity=False).hexdigest(),
        },
    }


@pytest.fixture
def platform(settings, api_data, archive):
    def handler(request):
        if request.url.path.endswith("pkg.zip"):
            assert "X-Bkapi-Authorization" not in request.headers
            return httpx.Response(200, content=archive)
        assert request.headers["X-Bk-Tenant-Id"] == "tenant"
        if "/agents/skill/" in request.url.path:
            assert request.url.params["agent_version"] == "1.0.0"
            data = api_data["skill"]
        else:
            assert request.url.params["version"] == "1.0.0"
            data = api_data["agent"]
        return httpx.Response(200, json={"result": True, "data": data})

    return PlatformClient(settings, httpx.MockTransport(handler))


@pytest_asyncio.fixture
async def adapter(settings, platform, monkeypatch):
    monkeypatch.setenv("AIDEV_ACCESS_TOKEN", "must-not-reach-child")
    settings.command = [sys.executable, str(Path(__file__).with_name("fake_agent.py"))]
    settings.prompt_timeout = 3
    instance = Adapter(settings, await ConfigSynchronizer(settings, platform).sync())
    yield instance
    await instance.close()
    await platform.close()


class ControlledConnection:
    def __init__(self):
        self.first_started = asyncio.Event()
        self.finish_first = asyncio.Event()
        self.cancel_entered = asyncio.Event()
        self.finish_cancel = asyncio.Event()
        self.second_started = asyncio.Event()

    async def new_session(self, **kwargs):
        return SimpleNamespace(session_id="controlled-session")

    async def prompt(self, session_id, prompt):
        if prompt[0].text == "first":
            self.first_started.set()
            await self.finish_first.wait()
        else:
            self.second_started.set()
        return SimpleNamespace(stop_reason="end_turn")

    async def cancel(self, **kwargs):
        self.cancel_entered.set()
        await self.finish_cancel.wait()


@pytest.fixture
def controlled_connection(adapter):
    connection = ControlledConnection()
    adapter._connection = connection
    return connection
