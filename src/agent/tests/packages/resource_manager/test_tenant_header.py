"""SDK 侧 ``X-Bk-Tenant-Id`` 租户头注入契约测试。

未显式传 tenant_id 时由 ``resolve_app_tenant_id()`` 兜底，头始终非空。
覆盖 ``AgentResourceManager.get_client`` / ``get_paas_sbx_client``（读 executor_info）
/ ``BkAgentApi.get_client``（子智能体）。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aidev_agent.api.constants import DEFAULT_TENANT_ID, MCP_ALLOWED_HEADERS_HEADER, TENANT_HEADER
from aidev_agent.packages.resource_manager.agent import AgentResourceManager


@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock(name="bkapi_client")


@pytest.fixture(autouse=True)
def _clear_app_tenant_env(monkeypatch):
    """隔离进程环境，确保兜底走 DEFAULT_TENANT_ID 而非宿主机注入值。"""
    monkeypatch.delenv("BKPAAS_APP_TENANT_ID", raising=False)


class TestAgentResourceManagerGetClient:
    """``AgentResourceManager.get_client`` 的租户头注入。"""

    @pytest.fixture(autouse=True)
    def _patch_bkaidev(self, mock_client, monkeypatch):
        from aidev_agent.packages.resource_manager import agent as agent_mod

        monkeypatch.setattr(agent_mod.BKAidevApi, "get_client", MagicMock(return_value=mock_client))
        # 避免 resolve_access_token 触发 bkoauth 查询
        monkeypatch.setattr(AgentResourceManager, "resolve_access_token", lambda self, username=None: "")

    def test_tenant_header_injected_when_present(self, mock_client):
        rm = AgentResourceManager(app_code="a", app_secret="s", tenant_id="tenant-x")
        rm.get_client()
        mock_client.update_headers.assert_called_once_with({TENANT_HEADER: "tenant-x"})

    def test_tenant_header_falls_back_to_default_when_omitted(self, mock_client):
        """未传 tenant_id：兜底默认租户（修复 tenant_mode=global 应用启动 403）。"""
        rm = AgentResourceManager(app_code="a", app_secret="s")
        rm.get_client()
        mock_client.update_headers.assert_called_once_with({TENANT_HEADER: DEFAULT_TENANT_ID})

    def test_tenant_header_falls_back_on_explicit_empty_string(self, mock_client):
        rm = AgentResourceManager(app_code="a", app_secret="s", tenant_id="")
        rm.get_client()
        mock_client.update_headers.assert_called_once_with({TENANT_HEADER: DEFAULT_TENANT_ID})

    def test_tenant_header_uses_paas_injected_app_tenant(self, mock_client, monkeypatch):
        """多租户应用：PaaS 注入 BKPAAS_APP_TENANT_ID 时取真实租户。"""
        monkeypatch.setenv("BKPAAS_APP_TENANT_ID", "tenant-real")
        rm = AgentResourceManager(app_code="a", app_secret="s")
        rm.get_client()
        mock_client.update_headers.assert_called_once_with({TENANT_HEADER: "tenant-real"})


class TestInjectTenantHeaderHelper:
    """``_inject_tenant_header`` 独立行为。"""

    def test_injects_default_when_not_specified(self, mock_client):
        rm = AgentResourceManager(app_code="a", app_secret="s")
        rm._inject_tenant_header(mock_client)
        mock_client.update_headers.assert_called_once_with({TENANT_HEADER: DEFAULT_TENANT_ID})

    def test_inject_on_present(self, mock_client):
        rm = AgentResourceManager(app_code="a", app_secret="s", tenant_id="t1")
        rm._inject_tenant_header(mock_client)
        mock_client.update_headers.assert_called_once_with({TENANT_HEADER: "t1"})


class TestPaasSbxClientTenant:
    """``get_paas_sbx_client`` 从 executor_info 读取 tenant_id。"""

    @pytest.fixture()
    def rm(self) -> AgentResourceManager:
        return AgentResourceManager(app_code="test-app", app_secret="test-secret")

    @pytest.fixture(autouse=True)
    def _patch_bkapi(self, mock_client, monkeypatch):
        from aidev_agent.packages.resource_manager import base as base_mod

        monkeypatch.setattr(base_mod.BkPaaSSandboxApi, "get_client", MagicMock(return_value=mock_client))
        monkeypatch.setattr(base_mod.BkPaaSSandboxApi, "get_client_by_username", MagicMock(return_value=mock_client))

    def test_tenant_injected_from_executor_info(self, rm, mock_client):
        rm.get_paas_sbx_client({"app_code": "a1", "app_secret": "s1", "executor": "alice", "tenant_id": "tenant-y"})
        mock_client.update_headers.assert_called_once_with({TENANT_HEADER: "tenant-y"})

    def test_tenant_not_injected_when_absent(self, rm, mock_client):
        rm.get_paas_sbx_client({"app_code": "a1", "app_secret": "s1", "executor": "alice"})
        mock_client.update_headers.assert_not_called()

    def test_tenant_not_injected_when_empty(self, rm, mock_client):
        rm.get_paas_sbx_client({"app_code": "a1", "app_secret": "s1", "executor": "alice", "tenant_id": ""})
        mock_client.update_headers.assert_not_called()


class TestBkAgentApiGetClientTenant:
    """``BkAgentApi.get_client`` 子智能体网关的租户头注入（父→子透传）。"""

    @pytest.fixture()
    def mock_client(self) -> MagicMock:
        return MagicMock(name="bk_agent_client")

    @pytest.fixture(autouse=True)
    def _patch_factory(self, mock_client, monkeypatch):
        from aidev_agent.api import bk_agent as bk_agent_mod

        monkeypatch.setattr(bk_agent_mod, "_get_client_by_settings", MagicMock(return_value=mock_client))
        monkeypatch.setattr(bk_agent_mod, "get_endpoint", MagicMock(return_value="http://host/bp-child/prod"))

    def test_tenant_injected_when_present(self, mock_client):
        from aidev_agent.api.bk_agent import BkAgentApi

        BkAgentApi.get_client(agent_code="child", app_code="a", app_secret="s", tenant_id="tenant-z")
        mock_client.update_headers.assert_called_once_with({TENANT_HEADER: "tenant-z"})

    def test_tenant_not_injected_when_empty(self, mock_client):
        from aidev_agent.api.bk_agent import BkAgentApi

        BkAgentApi.get_client(agent_code="child", app_code="a", app_secret="s")
        mock_client.update_headers.assert_not_called()


class TestBKAidevApiFactoryTenant:
    """``BKAidevApi`` 工厂层兜底：不经 ResourceManager 的裸 client 也必须带租户头。

    ``aidev_ai_blueking.views`` 等调用方直接用 ``BKAidevApi.get_client()``，
    不带头会被网关以 403 拒绝，故在工厂层统一注入。
    """

    def test_get_client_injects_default_tenant(self):
        from aidev_agent.api.bk_aidev import BKAidevApi

        client = BKAidevApi.get_client(app_code="a", app_secret="s")
        assert client.session.headers[TENANT_HEADER] == DEFAULT_TENANT_ID

    def test_get_client_uses_paas_injected_tenant(self, monkeypatch):
        from aidev_agent.api.bk_aidev import BKAidevApi

        monkeypatch.setenv("BKPAAS_APP_TENANT_ID", "tenant-real")
        client = BKAidevApi.get_client(app_code="a", app_secret="s")
        assert client.session.headers[TENANT_HEADER] == "tenant-real"

    def test_resource_manager_tenant_overrides_factory_default(self, monkeypatch):
        """ResourceManager 持有的精确租户必须覆盖工厂兜底值。"""
        monkeypatch.setattr(AgentResourceManager, "resolve_access_token", lambda self, username=None: "")
        rm = AgentResourceManager(app_code="a", app_secret="s", tenant_id="explicit-x")
        client = rm.get_client()
        assert client.session.headers[TENANT_HEADER] == "explicit-x"


class TestLLMGatewayTenantHeader:
    """LLM 网关 ``default_headers`` 的租户头。

    ``ChatModel`` / ``Embeddings`` 经 openai/httpx 出站（非 bkapi client），
    补全与 ``token_check`` 共用该 headers，不带头会被网关 403。
    """

    _URL = "https://llm-gateway.example.com/v1"

    def test_falls_back_to_default_tenant(self):
        from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel

        model = ChatModel.get_setup_instance(model="m", base_url=self._URL)
        assert model.default_headers[TENANT_HEADER] == DEFAULT_TENANT_ID

    def test_uses_paas_injected_tenant(self, monkeypatch):
        from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel

        monkeypatch.setenv("BKPAAS_APP_TENANT_ID", "tenant-real")
        model = ChatModel.get_setup_instance(model="m", base_url=self._URL)
        assert model.default_headers[TENANT_HEADER] == "tenant-real"

    def test_caller_provided_tenant_not_overwritten(self):
        """调用方已在 default_headers 指定租户时不被兜底值覆盖（setdefault 语义）。"""
        from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel

        model = ChatModel.get_setup_instance(model="m", base_url=self._URL, default_headers={TENANT_HEADER: "caller-x"})
        assert model.default_headers[TENANT_HEADER] == "caller-x"

    def test_explicit_tenant_id_wins(self, monkeypatch):
        """显式 tenant_id（业务租户）优先级最高：盖过应用兜底。对齐平台侧 workbench 语义。"""
        from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel

        monkeypatch.setenv("BKPAAS_APP_TENANT_ID", "app-tenant")
        model = ChatModel.get_setup_instance(model="m", base_url=self._URL, tenant_id="biz-tenant")
        assert model.default_headers[TENANT_HEADER] == "biz-tenant"

    def test_explicit_tenant_id_overrides_default_headers(self):
        """显式 tenant_id 也盖过 default_headers 中已有的租户头（业务租户为准）。"""
        from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel

        model = ChatModel.get_setup_instance(
            model="m", base_url=self._URL, tenant_id="biz-tenant", default_headers={TENANT_HEADER: "stale-x"}
        )
        assert model.default_headers[TENANT_HEADER] == "biz-tenant"

    def test_empty_explicit_tenant_falls_back(self, monkeypatch):
        """显式 tenant_id 为空串时退回应用兜底（不覆盖成空）。"""
        from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel

        monkeypatch.delenv("BKPAAS_APP_TENANT_ID", raising=False)
        model = ChatModel.get_setup_instance(model="m", base_url=self._URL, tenant_id="")
        assert model.default_headers[TENANT_HEADER] == DEFAULT_TENANT_ID


class TestConstructMcpTenantHeader:
    """``construct_mcp`` 的 blueapps MCP server 租户头注入契约。

    链路：SDK → 网关 → mcp-proxy → 业务网关。``X-Bk-Tenant-Id`` 只作用于第一跳，
    必须同时声明 ``X-Bkapi-Allowed-Headers``，网关才会把租户头透传到后端业务网关，
    否则全租户应用在第二跳被 403（CROSS_TENANT_FORBIDDEN）。
    """

    def _capture_client_config(self, rm, mcp_config):
        """运行 construct_mcp，捕获传给 MultiServerMCPClient 的 client_config。

        mock ``run_coro_sync`` 直接驱动传入的协程工厂（headers 已在此前同步组装完成），
        避免真实 MCP 异步加载链路（recording_span/gather）在测试环境挂起。
        """
        captured = {}

        def _fake_client(client_config, **kwargs):
            captured["config"] = client_config
            inst = MagicMock()
            inst.get_tools = AsyncMock(return_value=[])
            return inst

        def _fake_run(coro_factory):
            import asyncio

            return asyncio.new_event_loop().run_until_complete(coro_factory())

        with (
            patch(
                "aidev_agent.packages.resource_manager.base.MultiServerMCPClient",
                side_effect=_fake_client,
            ),
            patch(
                "aidev_agent.packages.resource_manager.base.run_coro_sync",
                side_effect=_fake_run,
            ),
        ):
            rm.construct_mcp(mcp_config=mcp_config, username="alice")
        return captured["config"]

    def test_blueapps_mcp_injects_tenant_and_allowed_headers(self):
        rm = AgentResourceManager(app_code="a", app_secret="s", tenant_id="tenant-x")
        rm.resolve_access_token = lambda username=None: ""
        mcp_config = {
            "srv": {"url": "https://gw/mcp/", "transport": "sse", "credential_type": "blueapps"},
        }

        client_config = self._capture_client_config(rm, mcp_config)
        headers = client_config["srv"]["headers"]
        assert headers[TENANT_HEADER] == "tenant-x"
        # 必须声明透传，否则网关不会把租户头带到第二跳
        assert headers[MCP_ALLOWED_HEADERS_HEADER] == TENANT_HEADER

    def test_blueapps_mcp_falls_back_to_default_tenant(self, monkeypatch):
        """未显式租户时兜底 default（全租户应用启动/无 request 场景）。"""
        monkeypatch.delenv("BKPAAS_APP_TENANT_ID", raising=False)
        rm = AgentResourceManager(app_code="a", app_secret="s")
        rm.resolve_access_token = lambda username=None: ""
        mcp_config = {"srv": {"url": "https://gw/mcp/", "transport": "sse", "credential_type": "blueapps"}}

        client_config = self._capture_client_config(rm, mcp_config)
        headers = client_config["srv"]["headers"]
        assert headers[TENANT_HEADER] == DEFAULT_TENANT_ID
        assert headers[MCP_ALLOWED_HEADERS_HEADER] == TENANT_HEADER
