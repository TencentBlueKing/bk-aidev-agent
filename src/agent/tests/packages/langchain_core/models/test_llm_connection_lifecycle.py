import pytest
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.utils import db_connection


def test_sync_model_releases_connection_before_and_after_failure(monkeypatch):
    events = []
    monkeypatch.setattr(db_connection, "release_idle_connections", lambda: events.append("release"))

    def generate(*args, **kwargs):
        events.append("generate")
        raise ValueError("boom")

    monkeypatch.setattr(ChatModel.__mro__[1], "_generate", generate)

    with pytest.raises(ValueError, match="boom"):
        ChatModel.model_construct()._generate()

    assert events == ["release", "generate", "release"]
