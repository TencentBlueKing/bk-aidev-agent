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

from django.core.management.base import BaseCommand

from aidev_bkplugin.utils import bkaidev_api_client


class Command(BaseCommand):
    help = "升级智能体会话到支持 AG-UI 协议（将历史会话从 v1 协议升级为 AG-UI v2 协议）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="每批次处理的数量，默认 500，范围 1-5000",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]

        if batch_size < 1 or batch_size > 5000:
            self.stderr.write(self.style.ERROR("batch_size 必须在 1-5000 范围内"))
            return

        self.stdout.write(f"正在提交会话升级任务，batch_size={batch_size}...")

        try:
            result = bkaidev_api_client.api.upgrade_agent_sessions(json={"batch_size": batch_size})
            if result.get("result") == "OK" or result.get("data", {}).get("result") == "OK":
                self.stdout.write(self.style.SUCCESS("会话升级任务已提交成功，任务将在后台异步执行"))
                self.stdout.write("提示：升级进度和结果请在 AIDev 平台查看")
            else:
                self.stdout.write(self.style.WARNING(f"任务提交结果：{result}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"提交升级任务失败：{e}"))
