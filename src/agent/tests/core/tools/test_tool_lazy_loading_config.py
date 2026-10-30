# -*- coding: utf-8 -*-
"""工具延迟加载配置项（REQ-1 / AC-16 / AC-19）。

配置在 ``config.py`` import 期由 environs 解析：未设置时取内置默认；
非法布尔 / 非整数抛 ``EnvValidationError``，阈值 < 1 抛 ``ValueError``——
两者都是进程启动失败。用例用独立子进程断言，避免污染当前进程的 import 缓存。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[3]

_DEFAULT_PROBE = (
    "import aidev_agent.config as c;print(c.BKAI_TOOL_LAZY_LOADING_ENABLED, c.BKAI_TOOL_LAZY_LOADING_THRESHOLD)"
)


def _run_in_subprocess(code: str, env_overrides: dict[str, str | None]) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("BKAI_TOOL_LAZY_LOADING_")}
    for key, value in env_overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(AGENT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


class TestLazyLoadingConfig:
    """开关与阈值只走环境变量，非法值在 import 期失败。"""

    def test_defaults_when_unset(self):
        """两个变量均未设置时默认关闭、阈值 30。"""
        result = _run_in_subprocess(
            _DEFAULT_PROBE,
            {"BKAI_TOOL_LAZY_LOADING_ENABLED": None, "BKAI_TOOL_LAZY_LOADING_THRESHOLD": None},
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "False 30"

    def test_explicit_values(self):
        """显式设置时按环境变量取值。"""
        result = _run_in_subprocess(
            _DEFAULT_PROBE,
            {"BKAI_TOOL_LAZY_LOADING_ENABLED": "true", "BKAI_TOOL_LAZY_LOADING_THRESHOLD": "5"},
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "True 5"

    def test_invalid_bool_fails_startup(self):
        """AC-16（偏差口径）：开关无法解析为布尔时 import 期失败。"""
        result = _run_in_subprocess(_DEFAULT_PROBE, {"BKAI_TOOL_LAZY_LOADING_ENABLED": "not-a-bool"})
        assert result.returncode != 0
        assert "BKAI_TOOL_LAZY_LOADING_ENABLED" in result.stderr

    def test_non_integer_threshold_fails_startup(self):
        """AC-16（偏差口径）：阈值非整数时 import 期失败。"""
        result = _run_in_subprocess(_DEFAULT_PROBE, {"BKAI_TOOL_LAZY_LOADING_THRESHOLD": "abc"})
        assert result.returncode != 0
        assert "BKAI_TOOL_LAZY_LOADING_THRESHOLD" in result.stderr

    def test_zero_threshold_fails_startup(self):
        """阈值下界校验：0 在 import 期抛 ValueError，信息含变量名与取值。"""
        result = _run_in_subprocess(_DEFAULT_PROBE, {"BKAI_TOOL_LAZY_LOADING_THRESHOLD": "0"})
        assert result.returncode != 0
        assert "BKAI_TOOL_LAZY_LOADING_THRESHOLD" in result.stderr
        assert "0" in result.stderr

    def test_negative_threshold_fails_startup(self):
        """阈值下界校验：-1 同样在 import 期失败。"""
        result = _run_in_subprocess(_DEFAULT_PROBE, {"BKAI_TOOL_LAZY_LOADING_THRESHOLD": "-1"})
        assert result.returncode != 0
        assert "BKAI_TOOL_LAZY_LOADING_THRESHOLD" in result.stderr

    def test_settings_proxy_exposes_values(self):
        """两个变量经 settings 代理暴露，消费方式与现有 BKAI_TOOL_* 开关一致。"""
        from aidev_agent.config import settings

        assert settings.BKAI_TOOL_LAZY_LOADING_ENABLED is False
        assert settings.BKAI_TOOL_LAZY_LOADING_THRESHOLD == 30
