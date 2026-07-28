import pytest
from aidev_ai_blueking.settings import _get_bkapp_saas_path


@pytest.mark.parametrize(
    ("environment", "run_ver", "app_code", "expected"),
    [
        (
            {
                "BKPAAS_MARKET_ENTRANCE_URL": "https://example.com/market/agent/?from=market#chat",
                "BKAPP_SAAS_PATH": "/legacy-path",
            },
            "open",
            "agent-app",
            "/market/agent",
        ),
        ({"BKAPP_SAAS_PATH": "/legacy-path"}, "open", "agent-app", "/legacy-path"),
        ({}, "ieod", "agent-app", ""),
        ({}, "open", "agent-app", "/agent-app"),
    ],
)
def test_get_bkapp_saas_path(monkeypatch, environment, run_ver, app_code, expected):
    monkeypatch.delenv("BKPAAS_MARKET_ENTRANCE_URL", raising=False)
    monkeypatch.delenv("BKAPP_SAAS_PATH", raising=False)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)

    assert _get_bkapp_saas_path(run_ver, app_code) == expected
