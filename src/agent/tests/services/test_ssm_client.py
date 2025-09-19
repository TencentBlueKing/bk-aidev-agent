import pytest
import responses
from aidev_agent.api.ssm_client import SSMClient

BASE_URL = "https://bkssm.sg.crosgame.com"
APP_CODE = "test_app"
APP_SECRET = "test_secret"


@pytest.fixture
def client():
    return SSMClient(BASE_URL, APP_CODE, APP_SECRET)


@responses.activate
def test_create_access_token_with_bk_token(client):
    responses.add(
        responses.POST,
        f"{BASE_URL}/api/v1/auth/access-tokens",
        json={"code": 0, "data": {"access_token": "token1"}, "message": "ok"},
        status=200,
    )
    result = client.create_access_token("authorization_code", "bk_login", bk_token="bk_token_value")
    print("生成 access_token 返回:", result)
    assert result["code"] == 0
    assert result["data"]["access_token"] == "token1"


@responses.activate
def test_create_access_token_client_credentials(client):
    responses.add(
        responses.POST,
        f"{BASE_URL}/api/v1/auth/access-tokens",
        json={"code": 0, "data": {"access_token": "token2"}, "message": "ok"},
        status=200,
    )
    result = client.create_access_token("client_credentials", "client")
    print("client_credentials 生成 access_token 返回:", result)
    assert result["code"] == 0
    assert result["data"]["access_token"] == "token2"


@responses.activate
def test_refresh_access_token(client):
    responses.add(
        responses.POST,
        f"{BASE_URL}/api/v1/auth/access-tokens/refresh",
        json={"code": 0, "data": {"access_token": "token3"}, "message": "ok"},
        status=200,
    )
    result = client.refresh_access_token("refresh_token_value")
    print("刷新 access_token 返回:", result)
    assert result["code"] == 0
    assert result["data"]["access_token"] == "token3"


@responses.activate
def test_verify_access_token(client):
    responses.add(
        responses.POST,
        f"{BASE_URL}/api/v1/auth/access-tokens/verify",
        json={"code": 0, "data": {"identity": {"username": "admin"}}, "message": "ok"},
        status=200,
    )
    result = client.verify_access_token("token1")
    print("校验 access_token 返回:", result)
    assert result["code"] == 0
    assert result["data"]["identity"]["username"] == "admin"
