# -*- coding: utf-8 -*-
"""``CrawSyncer``：agent ↔ craw 的周期读写任务。

一个周期（``run_cycle``）做两件事：

- **read**：HTTP 健康探测（``backend.health()``），可选读回 craw home 下的
  状态文件（``read_file``）；
- **write**：把平台 Agent 定义同步到 craw home（共享卷 / 同容器路径），逐个
  产物写入后读回校验。同步的粒度由 provider 决定：

  - ``soul_provider()`` → 只下发人设 ``SOUL.md``（最小形态，向后兼容）；
  - ``artifacts_provider()`` → 下发一组产物 ``{相对路径: 内容}``，用于把
    平台 Agent 的完整定义（Prompt / MCP / Skills）对齐到内核。配合
    :func:`agent_config_to_artifacts` 可直接把平台 ``AgentConfig`` 渲染成
    产物集。

两个 provider 可同时给出（``soul_provider`` 视作 ``SOUL.md`` 一项并入产物集）。

宿主接入：Django 应用把 ``run_cycle`` 挂 celery beat / 周期任务即可；
本地模拟用 ``run_forever(max_cycles=N)``。文件面要求 agent 与 craw 可见
同一目录（同容器、共享卷或同 Pod emptyDir），HTTP 面只要求可达
``BKAI_CRAW_API_URL``。

.. note::
   craw 内核**消费**这些产物（把 ``SOUL.md`` / ``agent-config.json`` 应用成
   运行时人设与工具）是部署侧机制（如 ``agent apply``），不在本层职责内；
   本层只保证把平台定义**如实落到** craw home 并读回校验。
   平台 ``AgentConfig`` 不含内核自身的 Memory（那是内核运行期状态），故
   本层同步 Prompt / MCP / Skills 三类，不含 Memory。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from aidev_agent.packages.craw.registry import CrawBackendProtocol, get_backend

_logger = getLogger(__name__)

HOME_ENV = "BKAI_CRAW_HOME"
INTERVAL_ENV = "BKAI_CRAW_SYNC_INTERVAL"
DEFAULT_SOUL_FILENAME = "SOUL.md"
DEFAULT_CONFIG_FILENAME = "agent-config.json"


@dataclass
class CrawSyncResult:
    """单个同步周期的结果（可直接序列化上报）。"""

    backend: str = ""
    started_at: float = 0.0
    health: dict = field(default_factory=dict)
    # 每个产物写入的字节数（相对路径 → bytes）；SOUL.md 也在其中
    artifacts_written: Dict[str, int] = field(default_factory=dict)
    # 所有已写产物读回是否一致（无产物时为 True）
    artifacts_verified: bool = True
    # 读回校验失败的产物相对路径（供排查具体损坏项）
    artifacts_failed: list = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        # 读回校验失败同样视为本周期失败，不能把损坏配置当成功
        return not self.error and bool(self.health.get("ok")) and self.artifacts_verified

    # ---- 向后兼容别名：老调用方按 SOUL 单文件读结果 ----
    @property
    def soul_written_bytes(self) -> int:
        return self.artifacts_written.get(DEFAULT_SOUL_FILENAME, 0)

    @property
    def soul_verified(self) -> bool:
        return DEFAULT_SOUL_FILENAME in self.artifacts_written and self.artifacts_verified


class CrawSyncer:
    """agent 对 craw 的周期读写器。

    :param backend: craw 后端实例；缺省按 env ``BKAI_CRAW_BACKEND`` 装配。
    :param home_dir: craw home 目录（文件面根）；缺省读 env ``BKAI_CRAW_HOME``，
        为空则本周期跳过文件写（纯 HTTP read）。
    :param soul_provider: 返回人设内容字符串的回调；产出写入 ``soul_filename``。
    :param artifacts_provider: 返回 ``{相对路径: 内容}`` 的回调；用于下发整组
        配置产物（Prompt / MCP / Skills）。与 ``soul_provider`` 可并存。
    :param interval: ``run_forever`` 周期秒；缺省读 env ``BKAI_CRAW_SYNC_INTERVAL``（默认 60）。
    :param soul_filename: 人设写入文件名（默认 ``SOUL.md``）。
    """

    def __init__(
        self,
        backend: Optional[CrawBackendProtocol] = None,
        home_dir: Optional[str] = None,
        soul_provider: Optional[Callable[[], str]] = None,
        artifacts_provider: Optional[Callable[[], Dict[str, str]]] = None,
        interval: Optional[float] = None,
        soul_filename: str = DEFAULT_SOUL_FILENAME,
    ) -> None:
        self.backend = backend or get_backend()
        self.home_dir = Path(home_dir or os.getenv(HOME_ENV) or "") if (home_dir or os.getenv(HOME_ENV)) else None
        self.soul_provider = soul_provider
        self.artifacts_provider = artifacts_provider
        if interval is None:
            try:
                interval = float(os.getenv(INTERVAL_ENV) or 60)
            except (TypeError, ValueError):
                interval = 60.0
        self.interval = interval
        self.soul_filename = soul_filename

    # ---------- read ----------

    def _resolve_in_home(self, relpath: str) -> Path:
        """把相对路径解析为 craw home 内的绝对路径，越界即拒绝。

        拒绝三类输入：绝对路径、``..`` 父目录跳转，以及经符号链接 resolve
        后落在 home 之外的目标（共享卷场景下 symlink escape 可越界读写）。

        :raises RuntimeError: 未配置 home_dir。
        :raises ValueError: 路径非法或越出 craw home。
        """
        if not self.home_dir:
            raise RuntimeError(f"craw home 未配置（参数 home_dir 或 env {HOME_ENV}）")
        rel = Path(relpath)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"非法产物路径（须为 craw home 内相对路径）: {relpath!r}")
        home = self.home_dir.resolve()
        target = (home / rel).resolve()
        if not target.is_relative_to(home):
            raise ValueError(f"产物路径越出 craw home（symlink escape）: {relpath!r}")
        return target

    def read_status(self) -> dict:
        """HTTP 面读：craw 健康状态。"""
        return self.backend.health()

    def read_file(self, relpath: str) -> Optional[str]:
        """文件面读：craw home 下相对路径的文本内容（不存在返回 None）。"""
        if not self.home_dir:
            return None
        target = self._resolve_in_home(relpath)
        if not target.is_file():
            return None
        return target.read_text(encoding="utf-8")

    # ---------- write ----------

    def write_artifact(self, relpath: str, content: str) -> Path:
        """文件面写：内容写入 craw home 下的相对路径（父目录自动创建）。

        :raises RuntimeError: 未配置 home_dir。
        :raises ValueError: 路径非法或越出 craw home。
        """
        target = self._resolve_in_home(relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def write_soul(self, content: str) -> Path:
        """文件面写：人设内容写入 ``soul_filename``（``write_artifact`` 的别名）。"""
        return self.write_artifact(self.soul_filename, content)

    def collect_artifacts(self) -> Dict[str, str]:
        """汇总本周期要下发的产物 ``{相对路径: 内容}``。

        ``artifacts_provider`` 的产出为基底，``soul_provider`` 的产出并入
        ``soul_filename``（若两者都给了 ``SOUL.md``，以 ``soul_provider`` 为准）。
        """
        artifacts: Dict[str, str] = {}
        if self.artifacts_provider:
            produced = self.artifacts_provider() or {}
            artifacts.update({k: v for k, v in produced.items() if v is not None})
        if self.soul_provider:
            content = self.soul_provider()
            if content:
                artifacts[self.soul_filename] = content
        return artifacts

    # ---------- 周期 ----------

    def run_cycle(self) -> CrawSyncResult:
        """执行一个同步周期：read（health）→ write（产物集）→ 逐个读回校验。"""
        result = CrawSyncResult(backend=self.backend.name, started_at=time.time())
        try:
            result.health = self.read_status()
            if self.home_dir:
                failed: "list[str]" = []
                for relpath, content in self.collect_artifacts().items():
                    self.write_artifact(relpath, content)
                    result.artifacts_written[relpath] = len(content.encode("utf-8"))
                    if self.read_file(relpath) != content:
                        failed.append(relpath)
                result.artifacts_failed = failed
                result.artifacts_verified = not failed
                if failed:
                    # 读回校验失败必须进入失败状态，不能把损坏配置当成功
                    result.error = f"产物读回校验失败: {', '.join(failed)}"
        except Exception as exc:
            _logger.exception("[CRAW-SYNC] cycle failed: %s", exc)
            result.error = str(exc)
        _logger.info(
            "[CRAW-SYNC] backend=%s health_ok=%s artifacts=%s verified=%s error=%s",
            result.backend,
            result.health.get("ok"),
            sorted(result.artifacts_written),
            result.artifacts_verified,
            result.error or "-",
        )
        return result

    def run_forever(self, max_cycles: Optional[int] = None) -> "list[CrawSyncResult]":
        """按 ``interval`` 周期执行；``max_cycles`` 限次（本地模拟 / 测试用）。"""
        results: "list[CrawSyncResult]" = []
        cycle = 0
        while max_cycles is None or cycle < max_cycles:
            results.append(self.run_cycle())
            cycle += 1
            if max_cycles is not None and cycle >= max_cycles:
                break
            time.sleep(self.interval)
        return results


def _get(config: Any, name: str, default: Any = None) -> Any:
    """从 pydantic 模型或 dict 里取字段，缺省回落。"""
    if isinstance(config, dict):
        return config.get(name, default)
    return getattr(config, name, default)


def render_soul(config: Any) -> str:
    """把平台 Agent 的 ``role_prompts`` 渲染成 ``SOUL.md`` 文本。

    ``role_prompts`` 为 ``[{"role": ..., "content": ...}, ...]``；无则回落到
    ``agent_name`` 的最简人设。
    """
    name = _get(config, "agent_name") or _get(config, "agent_code") or "agent"
    prompts = _get(config, "role_prompts") or []
    blocks = [str(p.get("content", "")).strip() for p in prompts if isinstance(p, dict) and p.get("content")]
    body = "\n\n".join(b for b in blocks if b)
    return f"# {name}\n\n{body}\n" if body else f"# {name}\n"


def agent_config_to_artifacts(
    config: Any,
    soul_filename: str = DEFAULT_SOUL_FILENAME,
    config_filename: str = DEFAULT_CONFIG_FILENAME,
) -> Dict[str, str]:
    """把平台 ``AgentConfig``（或等价 dict）渲染成 craw home 产物集。

    产出两个文件：

    - ``soul_filename``：人设文本，来自 ``role_prompts``；
    - ``config_filename``：机器可读的配置快照 JSON，聚合 Prompt / MCP / Skills
      三类（``mcp_server_config`` / ``related_skills`` / ``tool_codes`` 等），
      供内核侧 ``agent apply`` 消费。

    :param config: 平台 ``AgentConfig`` 实例或含同名字段的 dict。
    """
    snapshot = {
        "agent_code": _get(config, "agent_code"),
        "agent_name": _get(config, "agent_name"),
        "chat_model": _get(config, "chat_model"),
        "role_prompts": _get(config, "role_prompts") or [],
        "mcp_server_config": _get(config, "mcp_server_config") or {},
        "related_skills": _get(config, "related_skills") or [],
        "tool_codes": _get(config, "tool_codes") or [],
    }
    return {
        soul_filename: render_soul(config),
        config_filename: json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    }
