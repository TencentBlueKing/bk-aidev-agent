# -*- coding: utf-8 -*-
"""Tests for the sensitive-path deny list (aidev_agent.packages.security.file_safety)."""

from __future__ import annotations

import pytest
from aidev_agent.packages.security.file_safety import (
    deny_reason,
    is_sensitive_path,
)


@pytest.mark.parametrize(
    "path",
    [
        "/root/.ssh/id_rsa",
        "/home/alice/.ssh/id_ed25519.pub",
        "/root/.gnupg/secring.gpg",
        "/home/alice/.aws/credentials",
        "/workspace/.config/gh/hosts.yml",
        "/root/.kube/config",
    ],
)
def test_sensitive_dir_blocked(path):
    assert deny_reason(path) is not None
    assert is_sensitive_path(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "/app/.env",
        "/app/.env.production",
        "/app/.env.local",
    ],
)
def test_env_file_blocked(path):
    assert "环境变量" in deny_reason(path)


@pytest.mark.parametrize(
    "path",
    [
        "/workspace/id_rsa",
        "/workspace/id_ed25519",
        "/workspace/id_ecdsa.pub",
        "/workspace/id_dsa",
    ],
)
def test_private_key_file_blocked(path):
    assert "私钥" in deny_reason(path)


@pytest.mark.parametrize(
    "path",
    [
        "/workspace/server.pem",
        "/workspace/cert.p12",
        "/workspace/key.pem",
        "/workspace/keystore.jks",
    ],
)
def test_sensitive_suffix_blocked(path):
    assert deny_reason(path) is not None


@pytest.mark.parametrize(
    "path",
    [
        "/workspace/api_key.txt",
        "/workspace/private_key_backup.txt",
        "/workspace/app_secret.json",
    ],
)
def test_sensitive_keyword_blocked(path):
    assert "敏感关键字" in deny_reason(path)


@pytest.mark.parametrize(
    "path",
    [
        "/workspace/main.py",
        "/workspace/tokenizer.py",
        "/workspace/tokenize_utils.py",
        "/workspace/readme.md",
        "/workspace/src/agent.py",
    ],
)
def test_benign_path_allowed(path):
    assert deny_reason(path) is None
    assert is_sensitive_path(path) is False


def test_tilde_expanded():
    assert is_sensitive_path("~/.aws/credentials") is True
