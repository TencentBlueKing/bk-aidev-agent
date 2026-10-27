# -*- coding: utf-8 -*-
"""``AgentHelper.get_authorize_prompt`` 对话入口授权校验契约。"""

from unittest.mock import MagicMock, patch

import pytest
from aidev_bkplugin.constants import AUTHORIZE_PAGE_QUERY

# 必须在模块级拿到真实模块对象并用 patch.object：tests/views 下的用例会用假模块永久替换
# sys.modules["aidev_bkplugin.services.agent_helpers"]，按字符串路径 patch 会落到假模块上。
from aidev_bkplugin.services import agent_helpers

PING_URL = "https://apps.example.com/agent/bk_plugin/plugin_api/agent/ping/"
AUTHORIZE_URL = f"https://apps.example.com/agent/{AUTHORIZE_PAGE_QUERY}"


@pytest.mark.parametrize(
    "bkoauth_installed, access_token, saas_url, markdown, expected",
    [
        (False, "", "", False, ""),
        (True, "token", "", False, ""),
        (True, "", PING_URL, False, f"请先到 {AUTHORIZE_URL} 完成授权"),
        (True, "", PING_URL, True, f"请先到 [授权页]({AUTHORIZE_URL}) 完成授权"),
        (True, "", "", False, "请联系智能体管理员"),
    ],
)
def test_get_authorize_prompt(bkoauth_installed, access_token, saas_url, markdown, expected):
    rm = MagicMock()
    rm.resolve_access_token.return_value = access_token
    bkoauth = MagicMock() if bkoauth_installed else None
    with (
        patch.object(agent_helpers, "bkoauth", bkoauth),
        patch.object(agent_helpers.AgentConfigFetcher, "get_info", return_value={"saas_url": saas_url}),
    ):
        prompt = agent_helpers.AgentHelper.get_authorize_prompt(rm, "alice", markdown=markdown)

    if expected:
        assert expected in prompt
    else:
        assert prompt == ""
