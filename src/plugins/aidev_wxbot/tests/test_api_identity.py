import json
from unittest.mock import patch

import pytest
from aidev_wxbot.api import BkApi
from django.test import override_settings


@pytest.mark.parametrize(
    ("username", "payload", "expected"),
    [(None, {}, "ops-user"), (None, {"bk_username": "caller"}, "caller"), ("explicit", {}, "explicit")],
)
@override_settings(BK_ADMIN_USERNAME="ops-user")
def test_call_action_identity(username, payload, expected):
    api = BkApi()
    with patch("aidev_wxbot.api.requests.request") as request:
        request.return_value.status_code = 200
        request.return_value.json.return_value = {"code": 0}
        api.call_action("test", bk_username=username, json=payload)
    header = request.call_args.kwargs["headers"]["X-Bkapi-Authorization"]
    assert json.loads(header)["bk_username"] == expected
