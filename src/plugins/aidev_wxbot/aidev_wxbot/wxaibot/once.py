"""进程内「只做一次」登记簿。

长连接是常驻进程，用普通 set 记录「这个会话/中断已经处理过」会一直增长且没有回收点，
因此登记簿按插入顺序封顶淘汰。被淘汰的老 key 会失去保护，容量要覆盖单个进程在
企微可回复窗口（24 小时）内可能处理的会话量。
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any


class BoundedOnceRegistry:
    """线程安全、容量有限的一次性登记簿。"""

    def __init__(self, maxlen: int) -> None:
        self._maxlen = maxlen
        self._lock = threading.Lock()
        self._keys: OrderedDict[Any, None] = OrderedDict()

    def claim(self, key: Any) -> bool:
        """首次登记返回 True；已登记过返回 False。"""
        with self._lock:
            if key in self._keys:
                return False
            self._keys[key] = None
            while len(self._keys) > self._maxlen:
                self._keys.popitem(last=False)
            return True

    def release(self, key: Any) -> None:
        """登记后没有真正执行时回滚，让后续尝试仍能拿到名额。"""
        with self._lock:
            self._keys.pop(key, None)

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._keys

    def __len__(self) -> int:
        with self._lock:
            return len(self._keys)
