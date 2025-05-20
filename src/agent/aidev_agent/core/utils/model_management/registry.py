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

import os
import time
from abc import abstractmethod
from concurrent.futures import Future
from concurrent.futures.thread import ThreadPoolExecutor
from pathlib import PosixPath
from typing import Dict, Optional

import Pyro4
from environs import Env
from Pyro4 import Daemon
from Pyro4.core import Proxy
from wrapt import synchronized

from . import service
from .service import dedicated_service_daemon, get_service_proxy


class AlreadySetupError(Exception):
    pass


thread_pool = ThreadPoolExecutor()


class ServiceRegistry:
    """远程服务注册"""

    _configured = False
    env = Env()

    def __init__(self, auto_configure: bool = True) -> None:
        self.current_daemon: Optional[Daemon] = None
        self.current_daemon_future: Optional[Future] = None
        if auto_configure:
            self.configure()

    @synchronized
    @classmethod
    def configure(
        cls,
        host: Optional[str] = None,
        ns_host: Optional[str] = None,
        ns_port: Optional[int] = None,
        contents_dir: Optional[str] = None,
    ) -> None:
        """配置"""
        if not cls._configured:
            if cls.env.str("BCS_RANDHOSTPORT_HOSTIP", None):
                Pyro4.config.NATHOST = cls.env.str("BCS_RANDHOSTPORT_HOSTIP")
                host = host or "0.0.0.0"
            Pyro4.config.HOST = (
                host
                or cls.env.str("DISPATCHING_DEDICATED_SERVICE_HOST", None)
                or cls.env.str("DEDICATED_SERVICE_HOST", "localhost")
                or cls.env.str("MODEL_SERVICE_HOST", "localhost")
            )
            Pyro4.config.NS_HOST = (
                ns_host
                or cls.env.str("DISPATCHING_DEDICATED_SERVICE_NS_HOST", None)
                or cls.env.str("DEDICATED_SERVICE_NS_HOST", "")
                or cls.env.str("MODEL_MANAGEMENT_NS_HOST", "")
            )
            Pyro4.config.NS_PORT = (
                ns_port
                or cls.env.int("DISPATCHING_DEDICATED_SERVICE_NS_PORT", None)
                or cls.env.int("DEDICATED_SERVICE_NS_PORT", None)
                or cls.env.int("MODEL_MANAGEMENT_NS_PORT", None)
            )
            env_contents_dir = cls.env.str("DISPATCHING_DEDICATED_SERVICE_CONTENTS_DIR", None) or cls.env.str(
                "DEDICATED_SERVICE_CONTENTS_DIR", None
            )
            contents_dir = str(
                PosixPath(contents_dir)
                if contents_dir
                else (PosixPath(env_contents_dir) if env_contents_dir else PosixPath.cwd())
            )
            Pyro4.config.SSL_CACERTS = Pyro4.config.SSL_SERVERCERT = Pyro4.config.SSL_CLIENTCERT = (
                f"{contents_dir}/certs/cert.pem"
            )
            Pyro4.config.SSL_SERVERKEY = Pyro4.config.SSL_CLIENTKEY = f"{contents_dir}/certs/key.pem"
            encryption = (
                cls.env.str("MODEL_SERVICE_ENCRYPTION", None)
                or cls.env.str("DISPATCHING_DEDICATED_SERVICE_ENCRYPTION", None)
                or cls.env.str("DEDICATED_SERVICE_ENCRYPTION", "protocol_fernet")
            )
            if encryption != "ssl":
                Pyro4.config.SSL = False
                Pyro4.config.SSL_REQUIRECLIENTCERT = False
                if encryption in ("protocol_aes", "protocol_sm4", "protocol_fernet"):
                    service.CUSTOM_ENCRYPTION = encryption

    @synchronized
    def register(self, object_qualified_name_map: Dict, main_service_name: str, port=None):
        """注册服务对象"""
        if self.current_daemon:
            raise AlreadySetupError("服务已注册")
        if self.env.str("BCS_RANDHOSTPORT_HOSTIP", None):
            Pyro4.config.NATPORT = self.env.int("BCS_RANDHOSTPORT_FOR_CONTAINER_PORT_7000")
            port = port or 7000
        port = (
            port or self.env.int("DISPATCHING_DEDICATED_SERVICE_PORT", None) or self.env.int("DEDICATED_SERVICE_PORT")
        )
        try:
            self.current_daemon = dedicated_service_daemon(
                object_qualified_name_map, main_service_name, port=port, looping=False
            )
            self.current_daemon_future = thread_pool.submit(self.current_daemon.requestLoop)
            for i in range(10):
                if self.current_daemon_future.running():
                    break
                time.sleep(1)
            else:
                raise TimeoutError(f"{main_service_name}{object_qualified_name_map}注册未成功")
        except Exception:
            self.unregister()
            raise

    @synchronized
    def unregister(self):
        """反注册服务对象"""
        if self.current_daemon and self.current_daemon_future:
            if self.current_daemon:
                self.current_daemon.shutdown()
            for i in range(60):
                if self.current_daemon_future.done():
                    break
                time.sleep(1)
            else:
                raise TimeoutError("反注册未成功")
            self.current_daemon = None
            self.current_daemon_future = None

    def get(self, object_qualified_name: str, cached: bool) -> Proxy:
        """获取服务对象"""
        obj = get_service_proxy(object_qualified_name, cached)
        return obj


class LLMRegistry(ServiceRegistry):
    @synchronized
    def register(self, object_qualified_name_map: Dict, main_service_name: str, port=None):
        if not main_service_name.startswith("bkaidev_llm"):
            raise Exception(f"不合规的MainDedicatedServiceName: {main_service_name}")
        return super().register(
            object_qualified_name_map=object_qualified_name_map, main_service_name=main_service_name, port=port
        )


class RegistryPluginMixIn:
    """服务注册快捷工具"""

    # 服务注册的前缀
    SERVICE_PREFIX = os.environ.get("LLM_SERVICE_PREFIX", "bkaidev_llm")

    @property
    @abstractmethod
    def service_name(self):
        """服务名称"""

    def get_registered_object(self, cached: bool = False, service_name: None = None) -> Proxy:
        """获取已注册的object"""
        from .registry import LLMRegistry

        service_name = service_name or self.service_name
        return LLMRegistry().get(f"{self.SERVICE_PREFIX}.{service_name}", cached=cached)
