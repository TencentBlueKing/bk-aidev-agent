# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import json

from aidev_agent.utils.tracing import get_current_trace_id
from pydantic import BaseModel
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.status import is_success
from rest_framework.utils import encoders


class BKAIDevJSONRenderer(encoders.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        return super().default(obj)


def get_response_trace_id(request) -> str | None:
    """Resolve the request trace ID, falling back to the active OTel span."""

    return getattr(request, "otel_trace_id", None) or get_current_trace_id()


class APIRenderer(JSONRenderer):
    """
    统一的结构封装返回内容
    """

    SUCCESS_CODE = "success"
    encoder_class = BKAIDevJSONRenderer

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        统一处理返回数据
        """
        response = renderer_context["response"]
        trace_id = get_response_trace_id(renderer_context.get("request"))

        if is_success(response.status_code):
            response.status_code = status.HTTP_200_OK
            return super(APIRenderer, self).render(data, accepted_media_type, renderer_context)

        code = str(response.status_code)
        message = response.data
        errors = response.data

        if isinstance(response.data, dict):
            code = response.data["code"]
            message = response.data["message"]
            errors = response.data.get("data")
            if isinstance(message, dict):
                if error_message := message.get("message"):
                    message = error_message
                else:
                    message = self.pretty_dict(json.loads(json.dumps(message, cls=self.encoder_class)))

        res_data = {
            "error": {
                "code": code,
                "message": message,
                "data": errors,
                "trace_id": trace_id,
            },
            "trace_id": trace_id,
        }
        return super(APIRenderer, self).render(res_data, accepted_media_type, renderer_context)

    def pretty_dict(self, dict_data):  # pylint: disable=no-self-use
        """
        将字典转为字符串返回
        格式: {key}: {value}
        """
        if not isinstance(dict_data, dict) or not dict_data:
            return dict_data
        res = []
        ignore_keys = ["non_field_errors"]
        for key, value in dict_data.items():
            if isinstance(value, list):
                value = " ".join(value)
            res.append(value if key in ignore_keys else f"{key}:{value}")
        return "; ".join(res)
