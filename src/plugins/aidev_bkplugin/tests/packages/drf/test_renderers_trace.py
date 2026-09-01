import json
from types import SimpleNamespace

from aidev_bkplugin.packages.drf.renderers import APIRenderer, get_response_trace_id


def test_get_response_trace_id_falls_back_to_current_span(mocker):
    trace_id = "b" * 32
    mocker.patch("aidev_bkplugin.packages.drf.renderers.get_current_trace_id", return_value=trace_id)

    assert get_response_trace_id(SimpleNamespace()) == trace_id


def test_error_renderer_returns_current_trace_id(mocker):
    trace_id = "c" * 32
    mocker.patch("aidev_bkplugin.packages.drf.renderers.get_current_trace_id", return_value=trace_id)
    data = {"code": "invalid", "message": "bad request", "data": None}
    context = {
        "request": SimpleNamespace(),
        "response": SimpleNamespace(status_code=400, data=data),
    }

    content = APIRenderer().render(data, renderer_context=context)

    assert json.loads(content)["trace_id"] == trace_id
