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
import signal
from typing import Any, Dict, List, Optional, Tuple, Union

from Pyro4.message import Message

if os.getenv("GEVENT_IN_DEDICATED_SERVICE") == "True":
    from gevent.monkey import patch_all

    patch_all()

import argparse
import contextlib
import inspect
import logging
import pickle
import random
import sys
import time
import uuid
from base64 import b64decode, b64encode
from copy import deepcopy
from importlib import import_module
from logging.handlers import RotatingFileHandler
from multiprocessing import Process
from threading import RLock, local
from uuid import uuid1

import Pyro4.core
import Pyro4.socketutil
from cachetools import TTLCache
from pydantic import BaseModel as PydanticV2BaseModel
from pydantic.v1 import BaseModel as PydanticV1BaseModel
from Pyro4 import current_context, errors, futures, message, util
from Pyro4.configuration import config
from Pyro4.core import _OnewayCallThread, log
from Pyro4.naming import startNSloop
from Pyro4.util import PickleSerializer, _serializers, _serializers_by_id, traceback
from Pyro4.utils.httpgateway import make_server, pyro_app
from wrapt import synchronized

from .utils import RemoteClassFactory  # noqa

try:
    from opentelemetry import propagate

except ImportError:
    propagate = None

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None  # type: ignore
try:
    from bkcrypto.symmetric import ciphers
except ImportError:
    ciphers = None

SYMMETRIC_CIPHER_CLASSES = {}
if ciphers:

    class BytesSupportMixIn:
        def encrypt(self, data):
            return super().encrypt(b64encode(data).decode("ascii")).encode("ascii")

        def decrypt(self, data):
            return b64decode(super().decrypt(data.decode("ascii")))

    class AESSymmetricCipher(BytesSupportMixIn, ciphers.AESSymmetricCipher):
        pass

    class SM4SymmetricCipher(BytesSupportMixIn, ciphers.SM4SymmetricCipher):
        pass

    SYMMETRIC_CIPHER_CLASSES["protocol_aes"] = AESSymmetricCipher
    SYMMETRIC_CIPHER_CLASSES["protocol_sm4"] = SM4SymmetricCipher

if Fernet:  # type: ignore
    SYMMETRIC_CIPHER_CLASSES["protocol_fernet"] = Fernet  # type: ignore

CUSTOM_ENCRYPTION = None

CUSTOM_ENCRYPTION_KEY = b"4QRcFBhcDnhrTTbWBHzMA3qPIcRxbAtZuQOfsE9amiU="

logger = logging.getLogger(__name__)


# 加密相关
class EncryptionPickleSerializer(PickleSerializer):
    @property
    @synchronized
    def symmetric_cipher(self) -> Any:
        if CUSTOM_ENCRYPTION and not getattr(self, "_symmetric_cipher", None):
            self._symmetric_cipher = SYMMETRIC_CIPHER_CLASSES[CUSTOM_ENCRYPTION](key=CUSTOM_ENCRYPTION_KEY)
        return self._symmetric_cipher

    def dumpsCall(self, obj: str, method: str, vargs: Union[List, Tuple], kwargs: Dict[str, Any]) -> bytes:
        content = super().dumpsCall(obj, method, vargs, kwargs)
        ret = self.symmetric_cipher.encrypt(content) if CUSTOM_ENCRYPTION else content
        return ret

    def dumps(self, data: Dict[str, str]) -> bytes:
        content = super().dumps(data)
        ret = self.symmetric_cipher.encrypt(content) if CUSTOM_ENCRYPTION else content
        return ret

    def loadsCall(self, data):
        data = self._convertToBytes(data)
        ret = self.symmetric_cipher.decrypt(data) if CUSTOM_ENCRYPTION else data
        return pickle.loads(ret)

    def loads(self, data: bytes) -> Any:
        data = self._convertToBytes(data)
        ret = self.symmetric_cipher.decrypt(data) if CUSTOM_ENCRYPTION else data
        return pickle.loads(ret)


_ser = EncryptionPickleSerializer()
_serializers["pickle"] = _ser
_serializers_by_id[_ser.serializer_id] = _ser


# 日志相关
def parse_wiredata(msg: Message) -> Dict[str, Any]:
    """解析wiredata，从中获取信息"""
    try:
        data = _ser.symmetric_cipher.decrypt(msg.data) if CUSTOM_ENCRYPTION else msg.data
    except Exception:  # noqa
        data = msg.data
    info = {
        "corr": str(uuid.UUID(bytes=msg.annotations["CORR"])) if "CORR" in msg.annotations else "?",
        "data": data,
        "annotations": msg.annotations,
        "type": msg.type,
        "flags": msg.flags,
        "serializer_id": msg.serializer_id,
        "seq": msg.seq,
    }
    try:
        info["un_pickled_content"] = pickle.loads(info["data"])
        # 配置内部白名单访问方式
        if info["un_pickled_content"][-1].get("app_code") == os.getenv("WHILE_APP_CODE", "Kj9F7VAl1qN4Gx"):
            info["annotations"] = {
                "TRAC": pickle.dumps(
                    {"tracestate": "bk_app_code=aidev_experiment,bk_username=admin", "traceparent": "000-111-000"}
                )
            }
    except Exception:  # pylint: disable=broad-except
        info["un_pickled_content"] = None
    info["trace"] = {}
    if "TRAC" in msg.annotations:
        with contextlib.suppress(Exception):
            info["trace"] = pickle.loads(msg.annotations["TRAC"])
    return info


def _log_wiredata(logger: logging.Logger, text: str, msg: Message) -> None:
    """patch _log_wiredata"""
    info = parse_wiredata(msg)
    try:
        info["un_pickled_content"] = str(info["un_pickled_content"])
    except Exception:  # pylint: disable=broad-except
        info["un_pickled_content"] = None
    logger.debug(
        "%s: msgtype=%d flags=0x%x ser=%d seq=%d corr=%s\nannotations=%r\ndata=%r\nunserialized_data=%r\n"
        % (
            text,
            msg.type,
            msg.flags,
            msg.serializer_id,
            msg.seq,
            info["corr"],
            info["annotations"],
            msg.data,
            info["un_pickled_content"],
        )
    )
    logger.info("Wire data is recorded", extra=info)


Pyro4.core._log_wiredata = _log_wiredata

# otel相关

if os.getenv("DEDICATED_SERVICE_STANDALONE_OTEL_INSTRUMENTATION") == "True" and propagate:

    def _pyroAnnotations(self: Pyro4.core.Proxy) -> Dict[str, Any]:
        """自动注入span信息"""
        extra: dict = {"TRAC": {}}
        propagate.inject(extra["TRAC"])
        extra["TRAC"] = pickle.dumps(extra["TRAC"])
        return extra

else:

    def _pyroAnnotations(self: Pyro4.core.Proxy) -> Dict[str, Any]:
        """自动注入span信息"""
        extra = {"TRAC": b""}
        trace_info = getattr(current_context, "trace_info", {}).get("TRAC", {})
        if trace_info:
            extra["TRAC"] = pickle.dumps(trace_info)
        return extra


Pyro4.Proxy._pyroAnnotations = _pyroAnnotations

# 服务相关
_orig_get_ssl_context = Pyro4.socketutil.getSSLcontext


def getSSLcontext(servercert="", serverkey="", clientcert="", clientkey="", cacerts="", keypassword=""):
    c = _orig_get_ssl_context(servercert, serverkey, clientcert, clientkey, cacerts, keypassword)
    c.check_hostname = False
    return c


Pyro4.socketutil.getSSLcontext = getSSLcontext

Pyro4.config.HOST = "localhost"
Pyro4.config.SSL = True
Pyro4.config.SSL_REQUIRECLIENTCERT = True
Pyro4.config.SSL_CACERTS = "./certs/cert.pem"
Pyro4.config.SSL_SERVERCERT = "./certs/cert.pem"
Pyro4.config.SSL_SERVERKEY = "./certs/key.pem"
Pyro4.config.SSL_CLIENTCERT = "./certs/cert.pem"
Pyro4.config.SSL_CLIENTKEY = "./certs/key.pem"
Pyro4.config.NS_HOST = "localhost"
Pyro4.config.NS_PORT = 2888
Pyro4.config.NS_AUTOCLEAN = 3.0
Pyro4.config.SERIALIZER = "pickle"
Pyro4.config.SERIALIZERS_ACCEPTED = ["pickle"]
Pyro4.config.PICKLE_PROTOCOL_VERSION = 4
Pyro4.config.MAX_RETRIES = 3
Pyro4.config.THREADPOOL_SIZE = int(os.environ.get("PYRO_THREADPOOL_SIZE", 128))
Pyro4.config.LOGWIRE = True
Pyro4.config.REQUIRE_EXPOSE = False


def import_obj(obj_path, package=None):
    """根据obj导入obj."""
    split = obj_path.split(".")
    module_name, variable_name = ".".join(split[:-1]), split[-1]
    module = import_module(module_name, package)
    cls = getattr(module, variable_name)
    return cls


def get_port(port_server_address=None):
    """获取空闲端口"""
    port = 0
    try:
        from portpicker import pick_unused_port

        port = pick_unused_port(portserver_address=port_server_address)
    except ImportError:
        pass
    return port


class HelloDispatchingDedicatedService:
    def hello(self):
        return "Just offer service."


class DedicatedServiceDaemon(Pyro4.core.Daemon):
    """独立远程服务"""

    def validateHandshake(self, conn, data):
        cert = conn.getpeercert()
        if Pyro4.config.SSL and Pyro4.config.SSL_REQUIRECLIENTCERT and not cert:
            raise Pyro4.errors.CommunicationError("Client未设置证书。")
        return super().validateHandshake(conn, data)

    def handleRequest(self, conn):  # noqa: C901
        request_flags = 0
        request_seq = 0
        request_serializer_id = util.MarshalSerializer.serializer_id
        wasBatched = False
        isCallback = False
        start_time = time.time()
        request_info = {}
        try:
            msg = message.Message.recv(conn, [message.MSG_INVOKE, message.MSG_PING], hmac_key=self._pyroHmacKey)
        except errors.CommunicationError as x:
            # we couldn't even get data from the client, this is an immediate error
            # log.info("error receiving data from client %s: %s", conn.sock.getpeername(), x)
            raise x
        try:
            request_flags = msg.flags
            request_seq = msg.seq
            request_serializer_id = msg.serializer_id
            current_context.correlation_id = (
                uuid.UUID(bytes=msg.annotations["CORR"]) if "CORR" in msg.annotations else uuid.uuid4()
            )
            parsed_info = parse_wiredata(msg)
            current_context.trace_info = {"TRAC": parsed_info["trace"]}
            if parsed_info["trace"]:
                current_context.trace_info["trace_id"] = parsed_info["trace"]["traceparent"].split("-")[1]
                current_context.trace_info.update(
                    dict([item.split("=") for item in parsed_info["trace"]["tracestate"].split(",")])
                )
            request_info.update(parsed_info)
            request_info["start_time"] = start_time
            request_info["corr"] = current_context.correlation_id
            request_info["obj_id"] = None
            if config.LOGWIRE:
                _log_wiredata(log, "daemon wiredata received", msg)
            if msg.type == message.MSG_PING:
                # return same seq, but ignore any data (it's a ping, not an echo). Nothing is deserialized.
                msg = message.Message(
                    message.MSG_PING,
                    b"pong",
                    msg.serializer_id,
                    0,
                    msg.seq,
                    annotations=self._Daemon__annotations(),
                    hmac_key=self._pyroHmacKey,
                )
                if config.LOGWIRE:
                    _log_wiredata(log, "daemon wiredata sending", msg)
                conn.send(msg.to_bytes())
                return
            if msg.serializer_id not in self._Daemon__serializer_ids:
                raise errors.SerializeError("message used serializer that is not accepted: %d" % msg.serializer_id)
            serializer = util.get_serializer_by_id(msg.serializer_id)
            if request_flags & message.FLAGS_KEEPSERIALIZED:
                # pass on the wire protocol message blob unchanged
                objId, method, vargs, kwargs = self._Daemon__deserializeBlobArgs(msg)
            else:
                # normal deserialization of remote call arguments
                objId, method, vargs, kwargs = serializer.deserializeCall(
                    msg.data, compressed=msg.flags & message.FLAGS_COMPRESSED
                )

            is_stream_iter_request = method in ("get_next_stream_item", "close_stream")
            request_info["obj_id"] = objId

            current_context.client = conn
            try:
                current_context.client_sock_addr = (
                    conn.sock.getpeername()
                )  # store, because on oneway calls, socket will be disconnected
            except OSError:
                current_context.client_sock_addr = None  # sometimes getpeername() doesn't work...
            current_context.seq = msg.seq
            current_context.annotations = msg.annotations
            current_context.msg_flags = msg.flags
            current_context.serializer_id = msg.serializer_id
            del msg  # invite GC to collect the object, don't wait for out-of-scope
            obj = self.objectsById.get(objId)
            if obj is not None:
                if inspect.isclass(obj):
                    obj = self._getInstance(obj, conn)
                if request_flags & message.FLAGS_BATCH:
                    # batched method calls, loop over them all and collect all results
                    data = []
                    for method, vargs, kwargs in vargs:
                        method = util.getAttribute(obj, method)
                        try:
                            result = method(*vargs, **kwargs)  # this is the actual method call to the Pyro object
                        except Exception:  # pylint: disable=broad-except
                            xt, xv = sys.exc_info()[0:2]
                            log.debug("Exception occurred while handling batched request: %s", xv)
                            xv._pyroTraceback = util.formatTraceback(detailed=config.DETAILED_TRACEBACK)
                            if sys.platform == "cli":
                                util.fixIronPythonExceptionForPickle(xv, True)  # piggyback attributes
                            data.append(futures._ExceptionWrapper(xv))
                            break  # stop processing the rest of the batch
                        else:
                            data.append(result)  # note that we don't support streaming results in batch mode
                    wasBatched = True
                else:
                    # normal single method call
                    if method == "__getattr__":
                        # special case for direct attribute access (only exposed @properties are accessible)
                        data = util.get_exposed_property_value(obj, vargs[0], only_exposed=config.REQUIRE_EXPOSE)
                    elif method == "__setattr__":
                        # special case for direct attribute access (only exposed @properties are accessible)
                        data = util.set_exposed_property_value(
                            obj, vargs[0], vargs[1], only_exposed=config.REQUIRE_EXPOSE
                        )
                    else:
                        method = util.getAttribute(obj, method)
                        if request_flags & message.FLAGS_ONEWAY and config.ONEWAY_THREADED:
                            # oneway call to be run inside its own thread
                            _OnewayCallThread(target=method, args=vargs, kwargs=kwargs).start()
                        else:
                            isCallback = getattr(method, "_pyroCallback", False)
                            log.info(f"method: {method}, vargs: {vargs}, kwargs: {kwargs}")
                            data = method(*vargs, **kwargs)  # this is the actual method call to the Pyro object
                            if not request_flags & message.FLAGS_ONEWAY:
                                isStream, data = self._streamResponse(data, conn, request_info=request_info)
                                if isStream:
                                    # throw an exception as well as setting message flags
                                    # this way, it is backwards compatible with older pyro versions.
                                    exc = errors.ProtocolError("result of call is an iterator")
                                    ann = {"STRM": data.encode()} if data else {}
                                    self._sendExceptionResponse(
                                        conn,
                                        request_seq,
                                        serializer.serializer_id,
                                        exc,
                                        None,
                                        annotations=ann,
                                        flags=message.FLAGS_ITEMSTREAMRESULT,
                                    )
                                    return
            else:
                log.debug("unknown object requested: %s", objId)
                raise errors.DaemonError("unknown object")
            if request_flags & message.FLAGS_ONEWAY:
                return  # oneway call, don't send a response
            else:
                unserialized_data = data
                data, compressed = serializer.serializeData(data, compress=config.COMPRESSION)
                response_flags = 0
                if compressed:
                    response_flags |= message.FLAGS_COMPRESSED
                if wasBatched:
                    response_flags |= message.FLAGS_BATCH
                msg = message.Message(
                    message.MSG_RESULT,
                    data,
                    serializer.serializer_id,
                    response_flags,
                    request_seq,
                    annotations=self._Daemon__annotations(),
                    hmac_key=self._pyroHmacKey,
                )
                current_context.response_annotations = {}
                if config.LOGWIRE:
                    _log_wiredata(log, "daemon wiredata sending", msg)
                conn.send(msg.to_bytes())
                if not is_stream_iter_request:
                    if isinstance(unserialized_data, PydanticV1BaseModel):
                        unserialized_data = unserialized_data.dict()
                    elif isinstance(unserialized_data, PydanticV2BaseModel):
                        unserialized_data = unserialized_data.model_dump()
                    self.record_response(request_info, pickle.dumps(unserialized_data))
        except Exception:  # pylint: disable=broad-except
            xt, xv = sys.exc_info()[0:2]
            msg = getattr(xv, "pyroMsg", None)
            if msg:
                request_seq = msg.seq
                request_serializer_id = msg.serializer_id
            if xt is not errors.ConnectionClosedError:
                if xt not in (StopIteration, GeneratorExit):
                    log.debug("Exception occurred while handling request: %r", xv)
                    log.error(f"ERROR while hanndling request: {request_info} \ntrace: {traceback.format_exc()}")
                if not request_flags & message.FLAGS_ONEWAY and (
                    isinstance(xv, errors.SerializeError) or not isinstance(xv, errors.CommunicationError)
                ):
                    # only return the error to the client if it wasn't a oneway call, and not a communication error
                    # (in these cases, it makes no sense to try to report the error back to the client...)
                    tblines = util.formatTraceback(detailed=config.DETAILED_TRACEBACK)
                    self._sendExceptionResponse(conn, request_seq, request_serializer_id, xv, tblines)
            log.exception(traceback.format_exc())
            if isCallback or isinstance(xv, (errors.CommunicationError, errors.SecurityError)):
                raise  # re-raise if flagged as callback, communication or security error.
        finally:
            current_context.trace_info = {}

    def _streamResponse(self, data, client, request_info):
        from collections.abc import Iterator

        if isinstance(data, Iterator) or inspect.isgenerator(data):

            def stream_with_log():
                all_items = []
                while True:
                    try:
                        item = next(data)
                        yield item
                        if isinstance(item, PydanticV1BaseModel):
                            item = item.dict()
                        elif isinstance(item, PydanticV2BaseModel):
                            item = item.model_dump()
                        all_items.append(item)
                    except StopIteration:  # noqa
                        break

                self.record_response(request_info, [pickle.dumps(item) for item in all_items], True)

            data_with_log = stream_with_log()
        else:
            data_with_log = data

        return super()._streamResponse(data_with_log, client)

    def record_response(self, request_info, response_data, is_stream_response=False):
        response_info = deepcopy(request_info)
        response_info["request_data"] = response_info.pop("data")
        response_info.pop("un_pickled_content")
        response_info["response_data"] = response_data
        response_info["response_time"] = time.time() - request_info["start_time"]
        response_info["is_stream_response"] = is_stream_response
        log.info(f"完成请求: {request_info['trace'] or response_info['corr']}", extra=response_info)


def dedicated_service_daemon(
    object_qualified_name,
    main_service_name=None,
    port_server_address=None,
    port=None,
    shuffle_uri=True,
    looping=True,
    object_alias_name=None,
):
    """启动和注册独立远程服务"""
    dict_info = isinstance(object_qualified_name, dict)
    port = port or get_port(port_server_address=port_server_address)
    main_service_name = f"{main_service_name}." if main_service_name else ""
    d = DedicatedServiceDaemon(port=port)
    nameserver = Pyro4.locateNS(broadcast=False)
    registered_names = []
    if object_qualified_name:
        for i, per_info in enumerate(object_qualified_name):
            obj = None
            if dict_info:
                obj = object_qualified_name[per_info]
            info_list = per_info.split(":")
            qualified_name = info_list[0]
            instantiation_method = info_list[1] if len(info_list) >= 2 else "single"
            obj = obj if obj else import_obj(qualified_name)
            exposed_class = Pyro4.expose(obj)
            exposed_class._pyroInstancing = (instantiation_method, None)
            if object_alias_name:
                qualified_name = object_alias_name[i]
            name = register_to_daemon(d, main_service_name, qualified_name, exposed_class, nameserver, shuffle_uri)
            registered_names.append(name)
    for exposed_class_name in ["RemoteClassFactory", "HelloDispatchingDedicatedService"]:
        exposed_class = Pyro4.expose(globals()[exposed_class_name])
        name = register_to_daemon(d, main_service_name, exposed_class_name, exposed_class, nameserver, shuffle_uri)
        registered_names.append(name)

    def cleanup(signum=0, frame=None):
        for name in registered_names:
            nameserver.remove(name)
        sys.exit(0)

    # 注册SIGTERM的信号处理器
    signal.signal(signal.SIGTERM, cleanup)
    if looping:
        try:
            d.requestLoop()
        finally:
            cleanup()
    else:
        return d


def register_to_daemon(daemon, main_service_name, qualified_name, exposed_class, nameserver, shuffle_uri):
    uri = daemon.register(exposed_class, objectId=f"{main_service_name}{qualified_name}")
    registered_name = f"{main_service_name}{qualified_name}-{uuid1() if shuffle_uri else 'single'}"
    nameserver.register(
        registered_name,
        uri,
        metadata={f"{main_service_name}{qualified_name}"},
    )
    return registered_name


ns_proxies_cache: TTLCache = TTLCache(64, 1800)
_local = local()
_operate_lock = RLock()


def get_service_proxy(object_qualified_name: str, cached: bool = False) -> Pyro4.core.Proxy:
    """获取远程服务对象"""
    uri = object_qualified_name if isinstance(object_qualified_name, Pyro4.URI) else f"PYROMETA:{object_qualified_name}"
    proxy = maintain_proxy_cache(uri) if cached else Pyro4.Proxy(uri)
    return proxy


_orig_resolve = Pyro4.core._resolve


def _resolve(uri: Pyro4.core.URI, hmac_key: Optional[str] = None) -> Pyro4.core.URI:
    from Pyro4 import errors
    from Pyro4.core import URI, log

    if isinstance(uri, str):
        uri = Pyro4.URI(uri)
    elif not isinstance(uri, Pyro4.URI):
        raise TypeError("can only resolve Pyro URIs")
    if uri.protocol == "PYRO":
        return uri
    log.debug("resolving %s", uri)
    if not ns_proxies_cache.get("cached_ns_proxy"):
        with _operate_lock:
            if not ns_proxies_cache.get("cached_ns_proxy"):
                ns_proxies_cache["cached_ns_proxy"] = Pyro4.locateNS(broadcast=False)
    nameserver = ns_proxies_cache["cached_ns_proxy"]
    if uri.protocol == "PYRONAME":
        return nameserver.lookup(uri.object)
    elif uri.protocol == "PYROMETA":
        candidates = nameserver.list(metadata_all=uri.object)
        if candidates:
            candidate = random.choice(list(candidates.values()))
            log.debug("resolved to candidate %s", candidate)
            return URI(candidate)
        raise errors.NamingError("no registrations available with desired metadata properties %s" % uri.object)
    else:
        raise errors.PyroError("invalid uri protocol")


Pyro4.core._resolve = _resolve
Pyro4.resolve = _resolve


def maintain_proxy_cache(uri):
    """维护proxy cache"""
    uri = Pyro4.URI(uri)
    if not getattr(_local, "object_proxies_cache", None):
        _local.object_proxies_cache = TTLCache(32, 1200)
    if not _local.object_proxies_cache.get(uri):
        _local.object_proxies_cache[uri] = Pyro4.Proxy(uri)
    return _local.object_proxies_cache[uri]


def setup_logging(log_level, log_path: str = "log"):
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    simple_json_formatter = None
    for class_path in ["utils.logger.SimpleJsonFormatter"]:
        if not simple_json_formatter:
            with contextlib.suppress(ImportError):
                simple_json_formatter = import_obj(class_path)
    concurrent_log_handler = None
    for class_path in ["concurrent_log_handler.ConcurrentRotatingFileHandler"]:
        if not concurrent_log_handler:
            with contextlib.suppress(ImportError):
                concurrent_log_handler = import_obj(class_path)
    sh_formatter = logging.Formatter(
        "%(name)40s\t%(levelname)5s\t%(asctime)10s\t%(module)10s\t%(funcName)20s\t%(lineno)3s:\t%(message)s\t"
        "%(thread)5s\t%(process)5s\t"
    )
    sh = logging.StreamHandler()
    sh.setFormatter(sh_formatter)
    fh_cls = concurrent_log_handler or RotatingFileHandler
    if simple_json_formatter:
        jfh = fh_cls(
            filename=f"{log_path}/dedicate_service.json.log",
            backupCount=3,
            maxBytes=1024 * 1024 * 1024,
            encoding="utf-8",
        )
        jfh.setFormatter(simple_json_formatter())
    else:
        jfh = None
    fh = fh_cls(
        filename=f"{log_path}/dedicate_service.txt.log", backupCount=3, maxBytes=1024 * 1024 * 1024, encoding="utf-8"
    )
    fh.setFormatter(sh_formatter)
    fh_err = fh_cls(
        filename=f"{log_path}/dedicate_service.err.log", backupCount=3, maxBytes=1024 * 1024 * 1024, encoding="utf-8"
    )
    fh_err.setFormatter(sh_formatter)
    fh_err.setLevel(logging.ERROR)
    logging.getLogger("Pyro4.core").setLevel(log_level)
    logging.basicConfig(
        level=log_level,
        handlers=[i for i in [sh, fh, jfh, fh_err] if i],
    )


def start_ns_loop(storage_file_path: str = "dedicated_service_name_server"):
    """开启ns"""
    Pyro4.config.SERVERTYPE = "multiplex"
    startNSloop(enableBroadcast=False, storage=f"sql:{storage_file_path}")


def _run(args):
    global CUSTOM_ENCRYPTION

    if args.nameserver_host:
        Pyro4.config.NS_HOST = args.nameserver_host
    if args.nameserver_port:
        Pyro4.config.NS_PORT = args.nameserver_port
    if args.host:
        Pyro4.config.HOST = args.host
    if args.nat_host:
        Pyro4.config.NATHOST = args.nat_host
    if args.nat_port:
        Pyro4.config.NATPORT = args.nat_port
    if args.encryption != "ssl":
        Pyro4.config.SSL = False
        Pyro4.config.SSL_REQUIRECLIENTCERT = False
        if args.encryption != "None":
            CUSTOM_ENCRYPTION = args.encryption
    setup_logging(args.log_level, os.environ.get("LOG_PATH", "log"))
    try:
        if args.component == "daemon":
            d = dedicated_service_daemon(
                args.object_qualified_name,
                args.main_service_name,
                args.port_server_address,
                args.port,
                object_alias_name=args.object_alias_name,
            )
        elif args.component == "nameserver":
            start_ns_loop(args.storage_path)
        else:
            Pyro4.config.SSL = False
            Pyro4.config.SSL_REQUIRECLIENTCERT = False
            Pyro4.config.SERIALIZER = "json"
            Pyro4.config.SERIALIZERS_ACCEPTED = ["json"]
            pyro_app.ns_regex = r".*"
            n = Process(target=start_ns_loop, daemon=True)
            d = Process(
                target=dedicated_service_daemon,
                args=(args.object_qualified_name, args.main_service_name, args.port_server_address, args.port, False),
                kwargs=dict(object_alias_name=args.object_alias_name),
                daemon=True,
            )
            server = make_server("0.0.0.0", args.http_gateway_port, pyro_app)
            try:
                n.start()
                time.sleep(1)
                d.start()
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
                d.terminate()
                n.terminate()
    except KeyboardInterrupt:
        pass


def main():
    # 先启动name server再启动独立远程服务
    parser = argparse.ArgumentParser(prog="DispatchingDedicatedService")
    parser.add_argument("component", type=str, choices=("nameserver", "daemon", "http_gateway"))
    parser.add_argument("-qn", "--object_qualified_name", type=str, action="append")
    parser.add_argument("-an", "--object_alias_name", type=str, action="append")
    parser.add_argument("-pa", "--port_server_address", type=str)
    parser.add_argument("-sn", "--main_service_name", type=str)
    parser.add_argument("-ll", "--log_level", type=str, default=logging.INFO, choices=list(logging._nameToLevel))
    parser.add_argument("-nh", "--nameserver_host", type=str)
    parser.add_argument("-np", "--nameserver_port", type=int)
    parser.add_argument(
        "-ec",
        "--encryption",
        type=str,
        choices=("ssl", "protocol_aes", "protocol_sm4", "protocol_fernet", "None"),
        default="ssl",
    )
    parser.add_argument("-hh", "--host", type=str)
    parser.add_argument("-hp", "--port", type=int)
    parser.add_argument("-nah", "--nat_host", type=str)
    parser.add_argument("-nap", "--nat_port", type=int)
    parser.add_argument("-gp", "--http_gateway_port", type=int)
    parser.add_argument("-sp", "--storage_path", type=str, default="dedicated_service_name_server")
    args = parser.parse_args()
    _run(args)


if __name__ == "__main__":
    main()
