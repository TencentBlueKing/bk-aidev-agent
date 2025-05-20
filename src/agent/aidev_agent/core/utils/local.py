# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import uuid
from contextlib import contextmanager

from werkzeug.local import Local, release_local

__all__ = [
    "request_local",
    "inject_request_id",
    "request_local_injection",
    "release_request_local",
]

try:
    # 基于blueapps框架提供的request_local，中间件会自动对request_local进行清理
    from blueapps.utils.request_provider import request_local
except ImportError:
    # 未使用blueapps框架，使用了django框架，则需要自行实现local清理中间件
    request_local = Local()


def inject_request_id(local, http_request):
    """
    将request的对应id注入到local对象中，优先采用http_request中注入的request_id，否则生成一个新的id
    :param local: werkzeug.local对象
    :param http_request: request对象
    :return: None
    """
    request_meta = getattr(http_request, "META", {})
    x_request_id = request_meta.get("HTTP_X_REQUEST_ID") if isinstance(request_meta, dict) else None
    local.request_id = x_request_id or str(uuid.uuid4())


@contextmanager
def _with_request_local(context: dict):
    local_vars = {}
    for k in context:
        if hasattr(request_local, k):
            local_vars[k] = getattr(request_local, k)
            delattr(request_local, k)

    try:
        yield request_local
    finally:
        for k in context:
            if hasattr(request_local, k):
                delattr(request_local, k)
        for k, v in list(local_vars.items()):
            setattr(request_local, k, v)


@contextmanager
def request_local_injection(context: dict):
    with _with_request_local(context) as local:
        for k, v in context.items():
            setattr(local, k, v)
        yield


def release_request_local():
    release_local(request_local)
