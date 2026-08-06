# -*- coding: utf-8 -*-
"""``services/agent_*`` 共用 mock：拦截 ResourceManager 与其 client。

业务侧 ``SessionManager`` 内部通过 ``self._client()`` 取 client（``resource_manager().get_client()``）；
为避免单测真实 HTTP，本 conftest 把 ``SessionManager._client`` 替换为返回 ``MagicMock`` 的方法，
并替换模块内 ``resource_manager()`` 工厂。测试可断言 ``client.api.xxx`` 调用，或通过
``client.resource_manager_mock`` 断言 ResourceManager 的高层接口调用。
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_plugin_rm_client(monkeypatch):
    client = MagicMock()
    resource_manager_mock = MagicMock()
    resource_manager_mock.get_client.return_value = client
    client.resource_manager_mock = resource_manager_mock

    from aidev_bkplugin.services import agent_session

    monkeypatch.setattr(agent_session, "resource_manager", lambda: resource_manager_mock)
    monkeypatch.setattr(agent_session.SessionManager, "_client", lambda self: client)
    return client
