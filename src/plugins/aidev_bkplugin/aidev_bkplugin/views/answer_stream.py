# -*- coding: utf-8 -*-
"""只读回答流接口：``GET plugin_api/answer_stream/{trace_id}/``，返回 SSE。

运行中回放 Agent 的思考过程和正文；执行结束后返回会话记录中本次执行的思考过程。
与 ``schedule`` 接口相同，不做用户鉴权，靠 trace_id（BPF 生成的随机值）定位执行；只读，不影响执行。

配置（Django settings，均可选）：
- ``ANSWER_STREAM_OUTPUT_KEY``：流式内容对应的插件输出字段，默认 ``output``
- ``ANSWER_STREAM_MAX_SECONDS``：单连接最长时长，默认 30 分钟
- ``ANSWER_STREAM_EVENT_TYPES``：转发的 AG-UI 事件类型，默认正文和思考过程
"""

import logging

from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from aidev_bkplugin.services.answer_stream import (
    DEFAULT_EVENT_TYPES,
    StreamSettings,
    StreamUnsupported,
    TargetNotFound,
    history_answer,
    resolve_target,
    sse,
    stream_answer,
)

logger = logging.getLogger(__name__)


def _load_schedule(trace_id: str):
    from bk_plugin_framework.runtime.schedule.models import Schedule

    return Schedule.objects.filter(trace_id=trace_id).only("trace_id", "state", "data").first()


def _load_state(trace_id: str):
    from bk_plugin_framework.runtime.schedule.models import Schedule

    return Schedule.objects.filter(trace_id=trace_id).values_list("state", flat=True).first()


def _get_handler():
    from aidev_agent.services.messages_handler.factory import message_handler_factory

    handler = message_handler_factory.get()
    if not handler.supports_replay_from_start():
        raise StreamUnsupported("message handler does not support cross-process replay")
    return handler


def _load_contents(target) -> list:
    from aidev_bkplugin.services.agent_session import SessionManager

    return SessionManager(target.username).list_session_contents(target.session_code)


def _stream_settings() -> StreamSettings:
    return StreamSettings(
        output_key=getattr(settings, "ANSWER_STREAM_OUTPUT_KEY", "output"),
        max_duration=float(getattr(settings, "ANSWER_STREAM_MAX_SECONDS", 30 * 60)),
        event_types=frozenset(getattr(settings, "ANSWER_STREAM_EVENT_TYPES", DEFAULT_EVENT_TYPES)),
    )


def _sse_response(chunks, trace_id: str):
    """实时流和历史流共用发送、异常终止与关闭日志。"""

    def events():
        sent = 0
        try:
            for chunk in chunks:
                sent += 1
                yield chunk
        except Exception:
            logger.exception("[answer_stream] error trace_id=%s", trace_id)
            yield sse("end", {"reason": "error"})
        finally:
            logger.info("[answer_stream] close trace_id=%s events=%s", trace_id, sent)

    response = StreamingHttpResponse(events(), content_type="text/event-stream; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@login_exempt
@csrf_exempt
@require_GET
def answer_stream(request, trace_id: str):
    try:
        target = resolve_target(trace_id, _load_schedule(trace_id))
        if target.finished:
            # 执行已结束：从会话记录返回思考过程
            try:
                contents = _load_contents(target)
            except Exception:
                logger.exception("[answer_stream] load history failed trace_id=%s", trace_id)
                raise StreamUnsupported("execution finished")
            chunks = history_answer(target, contents, _stream_settings())
        else:
            handler = _get_handler()
            chunks = stream_answer(target, handler, lambda: _load_state(trace_id), _stream_settings())
    except TargetNotFound:
        return JsonResponse({"result": False, "reason": "not_found"}, status=404)
    except StreamUnsupported as e:
        return JsonResponse({"result": False, "reason": str(e)}, status=409)

    logger.info("[answer_stream] open trace_id=%s session_code=%s", trace_id, target.session_code)

    return _sse_response(chunks, trace_id)
