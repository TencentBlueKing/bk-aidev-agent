# -*- coding: utf-8 -*-
"""``AgentHelper.get_authorize_prompt`` 对话入口授权校验契约。"""

from unittest.mock import MagicMock, patch

import pytest
from aidev_bkplugin.constants import AUTHORIZATION_CHECK_ENV, AUTHORIZE_PAGE_QUERY

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


@pytest.mark.parametrize(
    "env_value, expected",
    [
        # 默认校验：未设置 / 空值 / 显式开启 / 无法识别的取值都校验
        (None, "请先到"),
        ("", "请先到"),
        ("  ", "请先到"),
        ("true", "请先到"),
        ("1", "请先到"),
        ("flase", "请先到"),
        # 仅显式配成假值（不分大小写、忽略首尾空格）才关闭
        ("false", ""),
        ("False", ""),
        (" FALSE ", ""),
        ("0", ""),
        ("no", ""),
        ("off", ""),
    ],
)
def test_get_authorize_prompt_env_switch(monkeypatch, env_value, expected):
    """默认校验；BKAI_AGENT_AUTHORIZATION_CHECK_ENABLED 仅在显式配成 false 等假值时关闭。"""
    if env_value is None:
        monkeypatch.delenv(AUTHORIZATION_CHECK_ENV, raising=False)
    else:
        monkeypatch.setenv(AUTHORIZATION_CHECK_ENV, env_value)
    rm = MagicMock()
    rm.resolve_access_token.return_value = ""
    with (
        patch.object(agent_helpers, "bkoauth", MagicMock()),
        patch.object(agent_helpers.AgentConfigFetcher, "get_info", return_value={"saas_url": PING_URL}),
    ):
        prompt = agent_helpers.AgentHelper.get_authorize_prompt(rm, "alice")

    if expected:
        assert expected in prompt
    else:
        assert prompt == ""
        rm.resolve_access_token.assert_not_called()
