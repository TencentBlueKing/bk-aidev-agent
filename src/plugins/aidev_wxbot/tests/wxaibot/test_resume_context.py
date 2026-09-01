import json
from unittest.mock import MagicMock

import pytest
from aidev_wxbot.wxaibot.resume_context import original_interrupt_turn


@pytest.mark.parametrize("encoded", [True, False])
def test_interrupt_retains_original_turn(encoded):
    content = {"interrupts": [{"id": "i1"}]}
    manager = MagicMock()
    manager.list_session_contents.return_value = [
        {"role": "interrupt", "property": {"turn_id": "t1"}, "content": json.dumps(content) if encoded else content}
    ]
    assert original_interrupt_turn(manager, "s1", "i1") == "t1"


@pytest.mark.parametrize(
    "record", [{"role": "user", "property": {"turn_id": "new-turn"}}, {"role": "interrupt", "content": "invalid"}]
)
def test_new_user_or_unrecognized_interrupt_is_not_resumed(record):
    manager = MagicMock()
    manager.list_session_contents.return_value = [record]
    with pytest.raises(ValueError):
        original_interrupt_turn(manager, "s1", "i1")
