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

from blueapps.utils.logger import logger
from django.conf import settings
from django.views.generic.base import View
from rest_framework.permissions import BasePermission
from rest_framework.request import Request


class ApigwPermission(BasePermission):
    def has_permission(self, request: Request, view: View):
        """验证应用来源是否合法"""
        if settings.ENVIRONMENT == "dev":
            return True

        if not hasattr(request, "app"):
            logger.error("request from apigw has no app info, details: %s", request.__dict__)
            return False

        if not hasattr(request.app, "verified"):
            logger.error("request from apigw has no verified info, details: %s", request.app.__dict__)
            return False

        return bool(request.app.verified)
