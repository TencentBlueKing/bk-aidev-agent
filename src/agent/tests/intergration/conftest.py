# -*- coding: utf-8 -*-
import pytest
from aidev_agent.api.bk_aidev import BKAidevApi


@pytest.fixture
def add_session():
    client = BKAidevApi.get_client()
    session_code = "onlyfortest1"
    client.api.create_chat_session(json={"session_code": session_code, "session_name": "testonly"})
    # 添加一些session content
    yield client, session_code
    result = client.api.get_chat_session_contents(params={"session_code": session_code})
    for each in result.get("data", []):
        _id = each["id"]
        client.api.destroy_chat_session_content(path_params={"id": _id})
    client.api.destroy_chat_session(path_params={"session_code": session_code})
