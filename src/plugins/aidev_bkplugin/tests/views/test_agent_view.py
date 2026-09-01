# -*- coding: utf-8 -*-

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

base_mod = types.ModuleType("aidev_bkplugin.views.base")
base_mod.PluginViewSet = object
sys.modules["aidev_bkplugin.views.base"] = base_mod

agent_config_mod = types.ModuleType("aidev_bkplugin.services.agent_config")
agent_config_mod.AgentConfigFetcher = MagicMock()
sys.modules["aidev_bkplugin.services.agent_config"] = agent_config_mod

agent_helpers_mod = types.ModuleType("aidev_bkplugin.services.agent_helpers")
agent_helpers_mod.AgentHelper = MagicMock()
sys.modules["aidev_bkplugin.services.agent_helpers"] = agent_helpers_mod

utils_mod = types.ModuleType("aidev_bkplugin.utils")
utils_mod.is_local_dev = lambda: False
utils_mod.set_user_access_token = MagicMock()
sys.modules["aidev_bkplugin.utils"] = utils_mod

from aidev_bkplugin.views import agent as agent_mod  # noqa: E402


def test_agent_info_keeps_role_template_and_variables(mocker):
    role_template = [{"role": "hidden-system", "content": "你是测试助手"}]
    role_variables = [{"field_name": "language", "field_value": "中文"}]
    agent_info = {
        "prompt_setting": {
            "collection_id": 1,
            "collection_content": role_template,
            "collection_variables": role_variables,
            "content": [
                {"role": "hidden-system", "content": "渲染后的系统提示词"},
                {"role": "pause", "content": "请问我可以帮你做什么？"},
            ],
        },
        "otel_info": "sensitive-otel-config",
    }
    get_info = mocker.patch.object(
        agent_mod.AgentConfigFetcher,
        "get_info",
        return_value=agent_info,
    )
    request = SimpleNamespace(query_params={}, user=SimpleNamespace(username="alice"))

    response = agent_mod.AgentInfoViewSet().info(request)

    assert response.data["prompt_setting"]["collection_id"] == 1
    assert response.data["prompt_setting"]["collection_content"] == role_template
    assert response.data["prompt_setting"]["collection_variables"] == role_variables
    assert response.data["prompt_setting"]["content"] == [{"role": "pause", "content": "请问我可以帮你做什么？"}]
    assert "otel_info" not in response.data
    get_info.assert_called_once_with(username="alice", app_code=None)
