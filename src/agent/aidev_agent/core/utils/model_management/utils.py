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

from pydantic import BaseModel

from aidev_agent.utils.module_loading import import_string


class RemoteClassFactory:
    class_path = NotImplemented

    def create(self, class_path=None, *args, **kwargs):
        class_path = self.class_path or class_path
        if class_path is NotImplemented:
            raise NotImplementedError("Class variable `class_path` is not set.")
        cls = import_string(class_path)
        obj = cls(*args, **kwargs)
        self._pyroDaemon.register(obj)
        return obj


class RemoteMixIn(BaseModel):
    def __getattr__(self, item):
        try:
            return self.__dict__[item]
        except KeyError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    def unregister_from_pyro_daemon(self):
        self._pyroDaemon.unregister(self)
