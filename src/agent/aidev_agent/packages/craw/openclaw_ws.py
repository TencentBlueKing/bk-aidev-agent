# -*- coding: utf-8 -*-
"""OpenClaw 网关 WebSocket 传输：驱动一次对话并产出结构化事件。

为什么不用 HTTP：两个 HTTP 端点都只给助手文本，拿不到内部工具（MCP、exec）活动。
``/v1/chat/completions`` 只有正文；``/v1/responses`` 的 function_call 输出项仅在
"由调用方执行工具"的模式下产生，而这里工具是 OpenClaw 自己执行的。工具事件由网关
按 ``registerToolEventRecipient(runId, connId)`` 定向投递给**发起该 run 的连接**，
旁听收不到，所以要拿工具事件就得自己用 WS 发起对话。

两个易踩空的点（缺任一都表现为"连上了但没有工具事件"）：

- 握手必须声明 ``tool-events`` 能力，否则网关静默不投工具帧；
- ``client.id`` / ``client.mode`` 受枚举约束，``mode: "operator"`` 会被 schema 拒
  （operator 是 role 不是 mode）。

本模块只做协议搬运，产出中立的 ``OpenClawEvent``，AG-UI 语义留给调用方翻译。
"""

import json
import threading
import uuid
from contextlib import suppress
from logging import getLogger
from typing import Generator, Optional

logger = getLogger(__name__)

# 取自内核 GATEWAY_CLIENT_IDS / GATEWAY_CLIENT_MODES / GATEWAY_CLIENT_CAPS。
# 用 gateway-client/backend 这组身份：协议文档载明同进程后端客户端在 loopback 上
# 以共享网关令牌鉴权时可免 device 配对，正是本代理与内核同容器的形态。
_CLIENT_ID = "gateway-client"
_CLIENT_MODE = "backend"
_CAP_TOOL_EVENTS = "tool-events"

_HANDSHAKE_TIMEOUT = 20.0


class OpenClawEvent:
    """网关事件的中立表示。

    ``kind`` 取 text / tool / thinking / done / error，其余字段按 kind 取用。
    """

    __slots__ = ("kind", "text", "phase", "tool_call_id", "tool_name", "args", "result", "is_error", "raw")

    def __init__(
        self,
        kind,
        *,
        text="",
        phase="",
        tool_call_id="",
        tool_name="",
        args=None,
        result=None,
        is_error=False,
        raw=None,
    ):
        self.kind = kind
        self.text = text
        self.phase = phase
        self.tool_call_id = tool_call_id
        self.tool_name = tool_name
        self.args = args
        self.result = result
        self.is_error = is_error
        self.raw = raw

    def __repr__(self):  # 便于排障时直接打印
        return f"<OpenClawEvent {self.kind} phase={self.phase!r} tool={self.tool_name!r}>"


class OpenClawWSError(RuntimeError):
    pass


class OpenClawWSSession:
    """一次对话 = 一条连接。用完即弃，避免跨请求共享状态。"""

    def __init__(self, url: str, token: str, timeout: float = 300.0):
        self.url = url
        self.token = token
        self.timeout = timeout
        self._ws = None
        self._run_id = ""
        self._closed = False

    # ---------------- 连接与握手 ----------------

    def connect(self) -> None:
        """握手；必要时以本地后端身份免鉴权重连。

        网关对"未绑定设备"的连接会清空声明的 scopes 但**仍然放行**，症状是握手
        ``ok: true``、随后 ``chat.send`` 报 ``missing scope``。同容器 loopback 上的
        ``gateway-client``/``backend`` 客户端可豁免设备配对：共享密钥匹配、或干脆
        不带鉴权。所以先带令牌试，授予的 scope 不足时按后者重连。
        """
        granted = self._handshake(with_auth=True)
        if "operator.write" in granted:
            return
        logger.warning("[OPENCLAW] 令牌未获授权（授予 scopes=%s），改以本地后端身份免鉴权重连", granted or [])
        self.close()
        self._closed = False
        granted = self._handshake(with_auth=False)
        if "operator.write" not in granted:
            raise OpenClawWSError(f"网关未授予 operator.write（授予 {granted or []}）")

    def _handshake(self, *, with_auth: bool) -> list:
        try:
            import websocket  # websocket-client
        except ImportError as exc:  # 依赖缺失时给出可操作的信息
            raise OpenClawWSError("缺少 websocket-client 依赖，无法走 WS 传输") from exc

        # 必须抑制 Origin：websocket-client 默认按 URL 自动带上，网关据此判定为
        # 浏览器来源，本地后端免配对豁免随即失效——表现为带令牌时 scopes 被清空、
        # 不带令牌时直接 "device identity required"。
        self._ws = websocket.create_connection(self.url, timeout=self.timeout, suppress_origin=True)
        # 网关先推 connect.challenge，收到后才发 connect
        deadline = threading.Event()
        timer = threading.Timer(_HANDSHAKE_TIMEOUT, deadline.set)
        timer.start()
        try:
            while not deadline.is_set():
                msg = self._recv_json()
                if msg is None:
                    continue
                if msg.get("event") == "connect.challenge":
                    self._send_connect(with_auth=with_auth)
                elif msg.get("type") == "res":
                    if not msg.get("ok"):
                        err = (msg.get("error") or {}).get("message", "unknown")
                        raise OpenClawWSError(f"握手被拒: {err}")
                    auth = (msg.get("payload") or {}).get("auth") or {}
                    return list(auth.get("scopes") or [])
            raise OpenClawWSError("握手超时")
        finally:
            timer.cancel()

    def _send_connect(self, *, with_auth: bool) -> None:
        params = {
            "minProtocol": 3,
            "maxProtocol": 4,
            "client": {"id": _CLIENT_ID, "version": "1.0.0", "platform": "linux", "mode": _CLIENT_MODE},
            "role": "operator",
            "scopes": ["operator.read", "operator.write"],
            # 不声明这个能力，网关不会投工具帧（握手依然成功）
            "caps": [_CAP_TOOL_EVENTS],
            "commands": [],
            "permissions": {},
            "locale": "zh-CN",
            "userAgent": "bkai-openclaw-proxy/1.0.0",
        }
        if with_auth and self.token:
            params["auth"] = {"token": self.token}
        self._send({"type": "req", "id": uuid.uuid4().hex, "method": "connect", "params": params})

    # ---------------- 收发 ----------------

    def _send(self, payload: dict) -> None:
        self._ws.send(json.dumps(payload))

    def _recv_json(self) -> Optional[dict]:
        raw = self._ws.recv()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        try:
            return json.loads(raw)
        except ValueError:
            return None  # ping 等非 JSON 帧不该中断消费

    def send_chat(self, session_key: str, message: str, *, agent_id: str = "") -> str:
        """发起一次对话，返回本次 run 的 id（用于过滤事件）。"""
        self._run_id = str(uuid.uuid4())
        params = {
            "sessionKey": session_key,
            "message": message,
            "idempotencyKey": self._run_id,
        }
        if agent_id:
            params["agentId"] = agent_id
        self._send({"type": "req", "id": uuid.uuid4().hex, "method": "chat.send", "params": params})
        return self._run_id

    # ---------------- 事件消费 ----------------

    def events(self) -> Generator[OpenClawEvent, None, None]:
        """产出本次 run 的事件，直到运行结束或出错。"""
        while True:
            try:
                msg = self._recv_json()
            except Exception as exc:
                if self._closed:
                    return
                yield OpenClawEvent("error", text=f"连接中断: {exc}")
                return
            if msg is None:
                continue

            mtype = msg.get("type")
            if mtype == "res":
                if not msg.get("ok"):
                    err = (msg.get("error") or {}).get("message", "unknown")
                    yield OpenClawEvent("error", text=err, raw=msg)
                    return
                continue

            if msg.get("event") != "agent":
                continue
            payload = msg.get("payload") or {}
            event = self._translate(payload)
            if event is None:
                continue
            yield event
            if event.kind in ("done", "error"):
                return

    def _translate(self, payload: dict) -> Optional[OpenClawEvent]:
        """把网关 agent 事件翻成中立事件。

        实测的帧词汇（``stream`` / ``data.phase``）：

        - ``lifecycle`` start|end —— 唯一的运行边界；``end`` 带 ``stopReason``。
          别拿其它流的 ``phase == "end"`` 当运行结束，那只是单个条目收尾。
        - ``assistant`` —— 正文增量在 ``data.delta``，**不带 phase**。
        - ``tool`` start|update|result —— ``result`` 阶段才带 ``data.result``
          与 ``isError``；``update`` 是执行中的局部输出，忽略以免重复计数。
        - ``item`` / ``command_output`` —— 面向 UI 的条目与命令输出，与 tool 流
          重复，这里不用。
        """
        stream = payload.get("stream")
        data = payload.get("data") or {}
        phase = data.get("phase") or ""

        if stream == "lifecycle":
            if phase == "end":
                return OpenClawEvent("done", phase=phase, raw=payload)
            return None

        if stream == "tool":
            if phase == "update":
                return None
            call_id = str(data.get("toolCallId") or data.get("callId") or "")
            return OpenClawEvent(
                "tool",
                phase=phase,
                tool_call_id=call_id,
                tool_name=data.get("name") or data.get("toolName") or "",
                args=data.get("args"),
                result=data.get("result"),
                is_error=bool(data.get("isError")),
                raw=payload,
            )

        if stream in ("assistant", "thinking"):
            text = data.get("delta")
            if isinstance(text, str) and text:
                return OpenClawEvent("thinking" if stream == "thinking" else "text", text=text, raw=payload)
        return None

    # ---------------- 收尾 ----------------

    def abort(self, session_key: str) -> None:
        if self._closed or not self._run_id:
            return
        try:
            self._send(
                {
                    "type": "req",
                    "id": uuid.uuid4().hex,
                    "method": "chat.abort",
                    "params": {"sessionKey": session_key, "runId": self._run_id},
                }
            )
        except Exception as exc:
            logger.warning("[OPENCLAW] abort 发送失败: %s", exc)

    def close(self) -> None:
        self._closed = True
        if self._ws is not None:
            with suppress(Exception):
                self._ws.close()
            self._ws = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False
