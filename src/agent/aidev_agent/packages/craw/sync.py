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

import contextlib
import errno
import fcntl
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from aidev_agent.packages.craw.registry import CrawBackendProtocol, get_backend

_logger = getLogger(__name__)

HOME_ENV = "BKAI_CRAW_HOME"
INTERVAL_ENV = "BKAI_CRAW_SYNC_INTERVAL"
ARTIFACT_MODE_ENV = "BKAI_CRAW_ARTIFACT_MODE"
DEFAULT_SOUL_FILENAME = "SOUL.md"
DEFAULT_CONFIG_FILENAME = "agent-config.json"
# staging / backup 与正式文件同目录，rename 才是原子的。文件名带周期 uuid，
# 重叠周期不会去删对方正在用的临时文件。
_STAGING_MARKER = ".craw-staging."
_BACKUP_MARKER = ".craw-backup."
_LOCK_NAME = ".craw-sync.lock"
# 产物含 MCP 认证 header 等敏感配置：staging/正式文件默认 0600，不依赖 umask。
# craw 内核与 agent 以不同 UID 跑在共享卷两侧时（同 Pod 双容器），0600 会挡住
# 内核消费——此时经参数 artifact_mode / env BKAI_CRAW_ARTIFACT_MODE 显式放宽（如 0644）。
_DEFAULT_ARTIFACT_MODE = 0o600


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
    # 本周期人设文件名（跟随 CrawSyncer.soul_filename，别名属性按它取数）
    soul_filename: str = DEFAULT_SOUL_FILENAME
    error: str = ""

    @property
    def ok(self) -> bool:
        # 读回校验失败同样视为本周期失败，不能把损坏配置当成功
        return not self.error and bool(self.health.get("ok")) and self.artifacts_verified

    # ---- 向后兼容别名：老调用方按 SOUL 单文件读结果 ----
    @property
    def soul_written_bytes(self) -> int:
        return self.artifacts_written.get(self.soul_filename, 0)

    @property
    def soul_verified(self) -> bool:
        return self.soul_filename in self.artifacts_written and self.artifacts_verified


@dataclass
class _StagedArtifact:
    relpath: str
    filename: str
    dirfd: int
    content: str
    staging_name: Optional[str] = None
    backup_name: Optional[str] = None
    committed: bool = False


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
    :param artifact_mode: 产物文件权限位；缺省读 env ``BKAI_CRAW_ARTIFACT_MODE``
        （八进制字符串，如 ``0644``），再缺省 0600。跨 UID 共享卷部署需放宽
        以便 craw 内核可读。
    """

    def __init__(
        self,
        backend: Optional[CrawBackendProtocol] = None,
        home_dir: Optional[str] = None,
        soul_provider: Optional[Callable[[], str]] = None,
        artifacts_provider: Optional[Callable[[], Dict[str, str]]] = None,
        interval: Optional[float] = None,
        soul_filename: str = DEFAULT_SOUL_FILENAME,
        artifact_mode: Optional[int] = None,
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
        if artifact_mode is None:
            raw_mode = (os.getenv(ARTIFACT_MODE_ENV) or "").strip()
            try:
                artifact_mode = int(raw_mode, 8) if raw_mode else _DEFAULT_ARTIFACT_MODE
            except ValueError:
                _logger.warning("[CRAW-SYNC] 非法 %s=%r，回落默认 0600", ARTIFACT_MODE_ENV, raw_mode)
                artifact_mode = _DEFAULT_ARTIFACT_MODE
        self.artifact_mode = artifact_mode

    @contextlib.contextmanager
    def _home_lock(self):
        """同一 craw home 的提交阶段互斥，避免重叠周期交错写入。"""
        if not self.home_dir:
            raise RuntimeError(f"craw home 未配置（参数 home_dir 或 env {HOME_ENV}）")
        fd = os.open(str(self.home_dir / _LOCK_NAME), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _is_temp_name(name: str) -> bool:
        return _STAGING_MARKER in name or _BACKUP_MARKER in name

    def _cleanup_temp_files(self) -> None:
        """持锁后清掉上一周期崩溃残留的 staging。backup 只在本周期成功提交后删除。"""
        if not self.home_dir:
            return
        for path in self.home_dir.rglob("*"):
            if path.is_file() and _STAGING_MARKER in path.name:
                with contextlib.suppress(OSError):
                    path.unlink()

    # ---------- read ----------

    def _validate_rel(self, relpath: str) -> Path:
        """校验产物相对路径：拒绝绝对路径、``..`` 父目录跳转与空路径。"""
        rel = Path(relpath)
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise ValueError(f"非法产物路径（须为 craw home 内相对路径）: {relpath!r}")
        return rel

    def _resolve_in_home(self, relpath: str) -> Path:
        """（读路径）把相对路径解析为 craw home 内的绝对路径，越界即拒绝。

        拒绝三类输入：绝对路径、``..`` 父目录跳转，以及经符号链接 resolve
        后落在 home 之外的目标。写路径不走本方法——resolve 校验与后续
        写入分离存在 TOCTOU 窗口，写路径用 ``_open_dir_in_home``（openat +
        O_NOFOLLOW，校验与打开同一系统调用）。

        :raises RuntimeError: 未配置 home_dir。
        :raises ValueError: 路径非法或越出 craw home。
        """
        if not self.home_dir:
            raise RuntimeError(f"craw home 未配置（参数 home_dir 或 env {HOME_ENV}）")
        rel = self._validate_rel(relpath)
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

    # ---------- write（openat + O_NOFOLLOW + staging 原子切换） ----------

    def _open_dir_in_home(self, dir_parts: "tuple[str, ...]") -> int:
        """从 craw home 起逐段 ``openat(O_NOFOLLOW | O_DIRECTORY)`` 下钻，返回目标目录 fd。

        「校验」与「打开」是同一个系统调用：路径上任何一段是符号链接都会
        被 O_NOFOLLOW 当场拒绝（不存在 resolve 后再写的 TOCTOU 窗口）；拿到
        fd 后的写入 / rename 全部经 ``dir_fd`` 进行，与路径字符串再无关系，
        共享卷上并发把父目录替换成 symlink 也无法把写入引出 home。
        缺失目录用 mkdirat 创建。调用方负责 ``os.close``。

        :raises RuntimeError: 未配置 home_dir。
        :raises ValueError: 路径中含符号链接段。
        """
        if not self.home_dir:
            raise RuntimeError(f"craw home 未配置（参数 home_dir 或 env {HOME_ENV}）")
        fd = os.open(str(self.home_dir), os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in dir_parts:
                with contextlib.suppress(FileExistsError):
                    os.mkdir(part, dir_fd=fd)
                try:
                    next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.EMLINK, errno.ENOTDIR):
                        raise ValueError(f"产物路径含符号链接/非目录段，拒绝写入: {part!r}") from exc
                    raise
                os.close(fd)
                fd = next_fd
        except BaseException:
            os.close(fd)
            raise
        return fd

    def _write_staging_at(self, dirfd: int, filename: str, content: str, cycle_id: str) -> str:
        """在目录 fd 下写 staging 文件（``artifact_mode``，O_EXCL + O_NOFOLLOW），返回 staging 名。"""
        staging_name = f".{filename}{_STAGING_MARKER}{cycle_id}"
        fd = os.open(
            staging_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, self.artifact_mode, dir_fd=dirfd
        )
        try:
            # O_CREAT 的 mode 受进程 umask 影响：显式 fchmod 落到目标权限，不依赖 umask
            os.fchmod(fd, self.artifact_mode)
        except OSError:
            os.close(fd)
            raise
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        return staging_name

    @staticmethod
    def _read_text_at(dirfd: int, filename: str) -> str:
        """经目录 fd 读文本（O_NOFOLLOW，staging 校验与切换后核验用）。"""
        fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dirfd)
        with os.fdopen(fd, "r", encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def _rename_at(dirfd: int, src: str, dst: str) -> None:
        os.rename(src, dst, src_dir_fd=dirfd, dst_dir_fd=dirfd)

    @staticmethod
    def _commit_at(dirfd: int, staging_name: str, filename: str) -> None:
        """staging → 正式文件原子切换（同目录 renameat，POSIX rename 覆盖语义）。"""
        os.rename(staging_name, filename, src_dir_fd=dirfd, dst_dir_fd=dirfd)

    def write_artifact(self, relpath: str, content: str) -> Path:
        """文件面写：staging 写入（0600）+ 读回校验 + 原子切换（父目录自动创建）。

        :raises RuntimeError: 未配置 home_dir。
        :raises ValueError: 路径非法（绝对路径 / ``..`` / 符号链接段）。
        """
        rel = self._validate_rel(relpath)
        with self._home_lock():
            dirfd = self._open_dir_in_home(rel.parts[:-1])
            staging_name = None
            try:
                staging_name = self._write_staging_at(dirfd, rel.name, content, uuid.uuid4().hex)
                if self._read_text_at(dirfd, staging_name) != content:
                    raise RuntimeError(f"staging 读回校验失败: {relpath}")
                self._commit_at(dirfd, staging_name, rel.name)
                staging_name = None
            except BaseException:
                if staging_name:
                    with contextlib.suppress(OSError):
                        os.unlink(staging_name, dir_fd=dirfd)
                raise
            finally:
                os.close(dirfd)
        return Path(self.home_dir) / rel  # type: ignore[arg-type]  # home_dir 已在 _open_dir_in_home 校验非空

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

    def _live_exists(self, dirfd: int, filename: str) -> bool:
        try:
            os.stat(filename, dir_fd=dirfd, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                return False
            raise

    def _rollback_commit(self, staged: "list[_StagedArtifact]") -> None:
        """commit 中途失败：撤掉已切换的新文件，把 backup 还原为正式文件。"""
        for entry in reversed(staged):
            if entry.committed:
                with contextlib.suppress(OSError):
                    os.unlink(entry.filename, dir_fd=entry.dirfd)
                entry.committed = False
            if entry.backup_name:
                with contextlib.suppress(OSError):
                    self._rename_at(entry.dirfd, entry.backup_name, entry.filename)
                entry.backup_name = None

    def _sync_artifacts(self, result: CrawSyncResult) -> None:
        """产物集事务同步：staging 全量校验 → 备份正式文件 → 切换 → 失败则完整回滚。

        阶段一任一产物失败时正式文件零改动。阶段二（正式文件 rename）若在
        第二个或后续文件失败，已切换的文件也会从 backup 还原，不会出现
        「新 SOUL + 旧 agent-config」的混合版本。同一 home 的提交持排它锁。
        """
        artifacts = self.collect_artifacts()
        if not artifacts:
            return
        cycle_id = uuid.uuid4().hex
        staged: "list[_StagedArtifact]" = []
        with self._home_lock():
            self._cleanup_temp_files()
            try:
                for relpath, content in artifacts.items():
                    rel = self._validate_rel(relpath)
                    dirfd = self._open_dir_in_home(rel.parts[:-1])
                    entry = _StagedArtifact(relpath=relpath, filename=rel.name, dirfd=dirfd, content=content)
                    staged.append(entry)
                    entry.staging_name = self._write_staging_at(dirfd, rel.name, content, cycle_id)
                    if self._read_text_at(dirfd, entry.staging_name) != content:
                        raise RuntimeError(f"staging 读回校验失败: {relpath}")
                for entry in staged:
                    if self._live_exists(entry.dirfd, entry.filename):
                        entry.backup_name = f".{entry.filename}{_BACKUP_MARKER}{cycle_id}"
                        self._rename_at(entry.dirfd, entry.filename, entry.backup_name)
                for entry in staged:
                    self._commit_at(entry.dirfd, entry.staging_name, entry.filename)
                    entry.staging_name = None
                    entry.committed = True
                    result.artifacts_written[entry.relpath] = len(entry.content.encode("utf-8"))
                for entry in staged:
                    if entry.backup_name:
                        with contextlib.suppress(OSError):
                            os.unlink(entry.backup_name, dir_fd=entry.dirfd)
                        entry.backup_name = None
            except BaseException:
                self._rollback_commit(staged)
                raise
            finally:
                for entry in staged:
                    if entry.staging_name:
                        with contextlib.suppress(OSError):
                            os.unlink(entry.staging_name, dir_fd=entry.dirfd)
                    os.close(entry.dirfd)
        failed = [relpath for relpath, content in artifacts.items() if self.read_file(relpath) != content]
        result.artifacts_failed = failed
        result.artifacts_verified = not failed
        if failed:
            result.error = f"产物读回校验失败: {', '.join(failed)}"

    def run_cycle(self) -> CrawSyncResult:
        """执行一个同步周期：read（health）→ write（产物集两阶段事务）→ 读回核验。"""
        result = CrawSyncResult(backend=self.backend.name, started_at=time.time(), soul_filename=self.soul_filename)
        try:
            result.health = self.read_status()
            if self.home_dir:
                self._sync_artifacts(result)
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
