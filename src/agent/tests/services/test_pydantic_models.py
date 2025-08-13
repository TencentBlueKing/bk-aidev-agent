from aidev_agent.services.pydantic_models import ChatPrompt, SessionContentExtra


def test_chat_prompt():
    chat_prompt = ChatPrompt(role="system", content="aaa", extra=SessionContentExtra(rendered_content="bbbb"))
    assert chat_prompt.content == "bbbb"

    chat_prompt = ChatPrompt(role="system", content="aaa")
    assert chat_prompt.content == "aaa"
