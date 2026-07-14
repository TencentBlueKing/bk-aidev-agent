# -*- coding: utf-8 -*-
"""``CrawSyncer``：agent ↔ craw 的周期读写任务。

一个周期（``run_cycle``）做两件事：

- **read**：HTTP 健康探测（``backend.health()``），可选读回 craw home 下的
  状态文件（``read_file``）；
- **write**：把人设 / 配置内容（``soul_provider()`` 产出，典型来源是平台
  agent 配置的 ``role_prompts``）写入 craw home（共享卷 / 同容器路径）的
  ``SOUL.md``，写后读回校验。

宿主接入：Django 应用把 ``run_cycle`` 挂 celery beat / 周期任务即可；
本地模拟用 ``run_forever(max_cycles=N)``。文件面要求 agent 与 craw 可见
同一目录（同容器、共享卷或同 Pod emptyDir），HTTP 面只要求可达
``BKAI_CRAW_API_URL``。
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path
from typing import Callable, Optional

from aidev_agent.packages.craw.registry import CrawBackendProtocol, get_backend

_logger = getLogger(__name__)

HOME_ENV = "BKAI_CRAW_HOME"
INTERVAL_ENV = "BKAI_CRAW_SYNC_INTERVAL"
DEFAULT_SOUL_FILENAME = "SOUL.md"


@dataclass
class CrawSyncResult:
    """单个同步周期的结果（可直接序列化上报）。"""

    backend: str = ""
    started_at: float = 0.0
    health: dict = field(default_factory=dict)
    soul_written_bytes: int = 0
    soul_verified: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.health.get("ok"))


class CrawSyncer:
    """agent 对 craw 的周期读写器。

    :param backend: craw 后端实例；缺省按 env ``BKAI_CRAW_BACKEND`` 装配。
    :param home_dir: craw home 目录（文件面根）；缺省读 env ``BKAI_CRAW_HOME``，
        为空则本周期跳过文件写（纯 HTTP read）。
    :param soul_provider: 返回人设内容字符串的回调；为空则不写 SOUL。
    :param interval: ``run_forever`` 周期秒；缺省读 env ``BKAI_CRAW_SYNC_INTERVAL``（默认 60）。
    :param soul_filename: 写入文件名（默认 ``SOUL.md``）。
    """

    def __init__(
        self,
        backend: Optional[CrawBackendProtocol] = None,
        home_dir: Optional[str] = None,
        soul_provider: Optional[Callable[[], str]] = None,
        interval: Optional[float] = None,
        soul_filename: str = DEFAULT_SOUL_FILENAME,
    ) -> None:
        self.backend = backend or get_backend()
        self.home_dir = Path(home_dir or os.getenv(HOME_ENV) or "") if (home_dir or os.getenv(HOME_ENV)) else None
        self.soul_provider = soul_provider
        if interval is None:
            try:
                interval = float(os.getenv(INTERVAL_ENV) or 60)
            except (TypeError, ValueError):
                interval = 60.0
        self.interval = interval
        self.soul_filename = soul_filename

    # ---------- read ----------

    def read_status(self) -> dict:
        """HTTP 面读：craw 健康状态。"""
        return self.backend.health()

    def read_file(self, relpath: str) -> Optional[str]:
        """文件面读：craw home 下相对路径的文本内容（不存在返回 None）。"""
        if not self.home_dir:
            return None
        target = self.home_dir / relpath
        if not target.is_file():
            return None
        return target.read_text(encoding="utf-8")

    # ---------- write ----------

    def write_soul(self, content: str) -> Path:
        """文件面写：人设内容写入 craw home 的 ``soul_filename``。

        :raises RuntimeError: 未配置 home_dir。
        """
        if not self.home_dir:
            raise RuntimeError(f"craw home 未配置（参数 home_dir 或 env {HOME_ENV}）")
        self.home_dir.mkdir(parents=True, exist_ok=True)
        target = self.home_dir / self.soul_filename
        target.write_text(content, encoding="utf-8")
        return target

    # ---------- 周期 ----------

    def run_cycle(self) -> CrawSyncResult:
        """执行一个同步周期：read（health）→ write（SOUL）→ 读回校验。"""
        result = CrawSyncResult(backend=self.backend.name, started_at=time.time())
        try:
            result.health = self.read_status()
            if self.soul_provider and self.home_dir:
                content = self.soul_provider()
                if content:
                    self.write_soul(content)
                    result.soul_written_bytes = len(content.encode("utf-8"))
                    result.soul_verified = self.read_file(self.soul_filename) == content
        except Exception as exc:
            _logger.exception("[CRAW-SYNC] cycle failed: %s", exc)
            result.error = str(exc)
        _logger.info(
            "[CRAW-SYNC] backend=%s health_ok=%s soul_bytes=%s verified=%s error=%s",
            result.backend,
            result.health.get("ok"),
            result.soul_written_bytes,
            result.soul_verified,
            result.error or "-",
        )
        return result

    def run_forever(self, max_cycles: Optional[int] = None) -> list[CrawSyncResult]:
        """按 ``interval`` 周期执行；``max_cycles`` 限次（本地模拟 / 测试用）。"""
        results: list[CrawSyncResult] = []
        cycle = 0
        while max_cycles is None or cycle < max_cycles:
            results.append(self.run_cycle())
            cycle += 1
            if max_cycles is not None and cycle >= max_cycles:
                break
            time.sleep(self.interval)
        return results
