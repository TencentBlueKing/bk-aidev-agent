# -*- coding: utf-8 -*-
"""PaaS Sandbox Client 离线单元测试（无需真实环境）。

真实接口联调请参考 `test_paas_client_real.py`（需 stag 环境凭证）。
"""

from unittest.mock import MagicMock, patch

from aidev_agent.api.paas_client import BkPaaSSandboxApi, Client


class TestClientPvFileOperations:
    """Client 类的 PV 文件相关 bind_property 静态检查。"""

    def test_client_has_list_files(self) -> None:
        """Client 类有 list_files 属性。"""
        assert hasattr(Client, "list_files")

    def test_client_has_delete_file(self) -> None:
        """Client 类有 delete_file 属性。"""
        assert hasattr(Client, "delete_file")

    def test_client_has_stat_file(self) -> None:
        """Client 类有 stat_file 属性。"""
        assert hasattr(Client, "stat_file")

    def test_client_has_preview_file(self) -> None:
        """Client 类有 preview_file 属性。"""
        assert hasattr(Client, "preview_file")

    def test_client_has_get_download_url(self) -> None:
        """Client 类有 get_download_url 属性。"""
        assert hasattr(Client, "get_download_url")


class TestPvFileOperationDefinitions:
    """PV 文件操作的路径、HTTP 方法解析正确性。

    通过 `Client()` 实例访问 bind_property 后，BindProperty.__get__ 会用
    保存的 kwargs 实例化 Operation 并 bind 到 client 上，此时可读 method / path。
    类级访问 `Client.list_files` 会返回 Operation 类本身，故不能用类访问断言。
    """

    @staticmethod
    def _get_operation(name: str):
        client = Client(endpoint="http://example.invalid")
        return getattr(client, name)

    def test_list_files_operation(self) -> None:
        op = self._get_operation("list_files")
        assert op.method == "GET"
        assert op.path == "agent_sandbox/applications/{app_code}/volumes/{volume_id}/files"

    def test_delete_file_operation(self) -> None:
        op = self._get_operation("delete_file")
        assert op.method == "DELETE"
        assert op.path == "agent_sandbox/applications/{app_code}/volumes/{volume_id}/files"

    def test_stat_file_operation(self) -> None:
        op = self._get_operation("stat_file")
        assert op.method == "GET"
        assert op.path == "agent_sandbox/applications/{app_code}/volumes/{volume_id}/files/stat"

    def test_preview_file_operation(self) -> None:
        op = self._get_operation("preview_file")
        assert op.method == "GET"
        assert op.path == "agent_sandbox/applications/{app_code}/volumes/{volume_id}/files/preview"

    def test_get_download_url_operation(self) -> None:
        op = self._get_operation("get_download_url")
        assert op.method == "GET"
        assert op.path == "agent_sandbox/applications/{app_code}/volumes/{volume_id}/files/download_url"


class TestBkPaaSSandboxApiGetClient:
    """BkPaaSSandboxApi.get_client 显式凭证传递正确性。"""

    @patch("aidev_agent.api.paas_client._get_client_by_settings")
    def test_get_client_passes_credentials(self, mock_get_client: MagicMock) -> None:
        """get_client(app_code=..., app_secret=...) 显式凭证正确转发。"""
        mock_client = MagicMock(spec=Client)
        mock_get_client.return_value = mock_client

        BkPaaSSandboxApi.get_client(app_code="bk-plugin-foo", app_secret="s3cret")

        call_kwargs = mock_get_client.call_args.kwargs
        assert call_kwargs["bk_app_code"] == "bk-plugin-foo"
        assert call_kwargs["bk_app_secret"] == "s3cret"
