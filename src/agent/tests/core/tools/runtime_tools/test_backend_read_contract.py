# -*- coding: utf-8 -*-
"""``RuntimeBackend.read`` 的跨后端统一契约（原始行数据 + 无损往返）。

背景（第一版实现的收敛修订）：后端**不再**接受 ``transform`` 回调，也**不再**
加展示行号。后端只负责「访问限制 → I/O → 按原文件 offset/limit 选行」，
返回 :class:`~aidev_agent.core.tools.runtime_tools.types.ReadResult`；
provider 统一做「``"\\n".join(lines)`` → 保行脱敏 → ``split("\\n")`` →
``format_content_with_line_numbers``」。

因此本文件钉住三条不变量：

1. **结果类型**：成功 ⇒ ``ReadResult``；返回型诊断 ⇒ ``str``；PaaS 的异常分支保持抛异常。
2. **无损往返**：``"\\n".join(result.lines).split("\\n") == result.lines``
   —— 必须用 ``split("\\n")`` 而非 ``splitlines()``，否则片段末尾的空行会丢。
3. **行号正确**：``result.start_line`` 是原文件中的 1-based 行号（非零 offset 时为
   ``offset + 1``），且后端返回的 ``lines`` 本身**不含**任何 ``行号 + TAB`` 前缀。

覆盖四个真实后端（local 同进程 / bubblewrap 沙箱 / e2b / paas）与一个**模拟后端**，
证明契约是「任何 RuntimeBackend 实现都要满足」的接口约定，而不是某个后端的巧合。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.tools.runtime_tools.bubblewrap_backend import BubblewrapFilesystemBackend
from aidev_agent.core.tools.runtime_tools.e2b_backend import E2BSandboxBackend
from aidev_agent.core.tools.runtime_tools.local_backend import FilesystemBackend
from aidev_agent.core.tools.runtime_tools.paas_backend import ExecResult, PaasSandboxBackend
from aidev_agent.core.tools.runtime_tools.types import ReadResult, RuntimeBackend
from aidev_agent.core.tools.runtime_tools.utils import LINE_NUMBER_WIDTH, format_content_with_line_numbers


def _has_line_number_prefix(lines: list[str]) -> bool:
    """判断后端返回的行里是否混入了 ``行号 + TAB`` 展示前缀。"""
    for line in lines:
        head = line[: LINE_NUMBER_WIDTH + 1]
        if "\t" in head and head.split("\t", 1)[0].strip().isdigit():
            return True
    return False


def _expected_lines(backend_name: str, content: str) -> list[str]:
    """某后端对「整文件内容 ``content``」必须产出的行列表。

    契约的核心是 **不得丢失任何真实空行**（``splitlines()`` 会丢末尾空行，
    这正是要避免的）。文件末尾的那个换行是**行终止符**而非独立一行，
    两种等价的行模型都能满足：

    - ``split("\\n")``：保留终止符产生的最后一个 ``""``（local / bwrap / e2b / mock，
      它们在进程内直接持有 ``content`` 字符串）；
    - ``split("\\n")`` 去掉终止符产生的尾部 ``""``（PaaS：远端 ``awk print $0``
      逐行输出、每行一个 ``\\n``，stdout 末尾的换行是「某行的终止符」，
      精确剥离一个后文件末尾的终止符自然消失 —— 这是 ``awk`` 的行模型）。

    两者都满足**不动点** ``"\\n".join(lines).split("\\n") == lines``，
    且都不丢真实空行；差异只在「文件最后一个字节是换行时，末尾那个空串」。
    """
    lines = content.split("\n")
    if backend_name == "paas" and lines and lines[-1] == "":
        return lines[:-1]
    return lines


def _assert_read_contract(result: ReadResult, *, first_line: int) -> None:
    """三条不变量的共用断言（供所有后端的参数化用例复用）。"""
    assert isinstance(result, ReadResult)
    assert isinstance(result.lines, list)
    assert all(isinstance(line, str) for line in result.lines)
    assert result.start_line == first_line
    # 后端不得越权做展示修饰
    assert not _has_line_number_prefix(result.lines)
    # 无损往返：join 后再 split 是不动点（用 split("\n")，不是 splitlines()）
    assert "\n".join(result.lines).split("\n") == result.lines


def _render(result: ReadResult) -> str:
    """模拟 provider 的展示步骤：脱敏之后再加行号。"""
    return format_content_with_line_numbers(result.lines, start_line=result.start_line)


# ---------------------------------------------------------------------------
# 模拟后端：证明契约对**非内置**实现同样成立
# ---------------------------------------------------------------------------


class _MockBackend(RuntimeBackend):
    """最小 RuntimeBackend 实现，只覆盖 read，用于验证接口约定的普适性。"""

    def __init__(self, content: str) -> None:
        self._content = content

    def read(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
        *,
        config=None,
        state=None,
    ) -> ReadResult | str:
        lines = self._content.split("\n")
        if offset >= len(lines):
            return f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)"
        return ReadResult(lines=lines[offset : offset + limit], start_line=offset + 1)


# ---------------------------------------------------------------------------
# 后端夹具
# ---------------------------------------------------------------------------


@dataclass
class _DummyE2BFiles:
    content: str

    def exists(self, path: str) -> bool:
        return True

    def read(self, path: str, format: str = "text"):
        return self.content


@dataclass
class _DummyE2BSandbox:
    files: _DummyE2BFiles


def _local_backend(tmp_path) -> FilesystemBackend:
    return FilesystemBackend(root_dir=str(tmp_path))


def _bwrap_backend(tmp_path) -> BubblewrapFilesystemBackend:
    backend = BubblewrapFilesystemBackend(root_dir=str(tmp_path))
    fake = MagicMock()
    backend._read_text = fake.read_text
    backend._available = True
    return backend


def _e2b_backend(content: str) -> E2BSandboxBackend:
    backend = E2BSandboxBackend()
    backend._ensure_sandbox = lambda: _DummyE2BSandbox(files=_DummyE2BFiles(content))  # type: ignore[method-assign]
    return backend


def _paas_backend() -> PaasSandboxBackend:
    backend = PaasSandboxBackend(
        app_code="test-app",
        bk_username="u",
        client=MagicMock(),
        snapshot="snap",
        snapshot_entrypoint=[],
        env_vars={},
    )
    # 绕过 _paas_error_enhance，使异常以原始类型抛出；异常语义本文件另行断言
    unwrapped = getattr(type(backend), "read").__wrapped__
    backend._ensure_sandbox = lambda **kw: "mock-sandbox-id"  # type: ignore[method-assign]
    backend.read = lambda *a, **kw: unwrapped(backend, *a, **kw)  # type: ignore[method-assign]
    return backend


def _paas_exec_handler(content: str):
    """模拟远端 shell：``test -f`` / ``END{print NR}`` / ``awk`` 真分页。

    ``awk`` 只做 ``print $0``（无行号）—— 与真实后端发出的命令一致。
    ``awk`` 的行模型是「每行以 ``\\n`` 结尾」，故文件末尾那个终止符不会
    额外产生一行（真机 awk 行为经实测确认）。
    """
    file_lines = content.split("\n")
    if file_lines and file_lines[-1] == "":
        file_lines = file_lines[:-1]

    def handler(sandbox_id, cmd, **kw):
        if cmd.startswith("test -f "):
            return ExecResult(stdout="", stderr="", exit_code=0)
        if "END{print NR}" in cmd:
            return ExecResult(stdout=f"{len(file_lines)}\n", stderr="", exit_code=0)
        if cmd.startswith("awk "):
            start = int(re.search(r"-v start=(\d+)", cmd).group(1))
            end = int(re.search(r"-v end=(\d+)", cmd).group(1))
            return ExecResult(
                stdout="".join(f"{ln}\n" for ln in file_lines[start - 1 : end - 1]),
                stderr="",
                exit_code=0,
            )
        return ExecResult(stdout="", stderr="", exit_code=0)

    return handler


def _make_backends(tmp_path, content: str) -> dict[str, tuple[object, str]]:
    """构造五个后端 + 该后端看到的文件全文。

    返回值：``{名字: (backend, 文件全文)}``。
    """
    (tmp_path / "f.txt").write_text(content, encoding="utf-8")

    paas = _paas_backend()
    paas.exec_command = _paas_exec_handler(content)

    bwrap_backend = _bwrap_backend(tmp_path)
    bwrap_backend._read_text.return_value = content

    return {
        "local": (_local_backend(tmp_path), content),
        "bwrap": (bwrap_backend, content),
        "e2b": (_e2b_backend(content), content),
        "paas": (paas, content),
        "mock": (_MockBackend(content), content),
    }


_ALL_BACKENDS = ["local", "bwrap", "e2b", "paas", "mock"]


# ---------------------------------------------------------------------------
# 无损往返 / 空行契约
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend_name", _ALL_BACKENDS)
@pytest.mark.parametrize(
    "content",
    [
        "only",  # 无尾换行：单行
        "a\nb\nc",  # 无尾换行：多行
        "a\nb\n",  # 有尾换行
        "a\n\n",  # 末尾空行（splitlines() 会吞掉的那个）
        "a\n\n\n",  # 末尾两个空行
        "head\n\nbody\n",  # 内部空行
    ],
)
def test_read_round_trips_without_losing_blank_lines(tmp_path, backend_name, content):
    """不得丢失任何真实空行；``join`` 后再 ``split("\\n")`` 必须是不动点。"""
    backends = _make_backends(tmp_path, content)
    backend, _ = backends[backend_name]

    result = backend.read("f.txt")

    assert isinstance(result, ReadResult), f"{backend_name} 应返回 ReadResult，实际 {type(result)}"
    assert result.lines == _expected_lines(backend_name, content), f"{backend_name} 行切分错误"
    # 关键回归：splitlines() 在这里会丢行
    assert len(result.lines) >= len(content.splitlines()), f"{backend_name} 丢了空行"
    _assert_read_contract(result, first_line=1)


@pytest.mark.parametrize(
    ("backend_name", "content"),
    [
        ("local", ""),
        ("local", "\n"),
        ("bwrap", ""),
        ("bwrap", "\n"),
        ("e2b", ""),
        ("paas", ""),
    ],
)
def test_empty_file_is_diagnostic_string(tmp_path, backend_name, content):
    """「空文件」仍是 ``check_empty_content`` 提示，且**不是** ReadResult。

    覆盖各族既有语义：
    - local / bwrap：``check_empty_content(content)`` 判 ``strip()`` 为空 ⇒
      0 字节与纯换行都命中；
    - e2b：判 ``if not content`` ⇒ 仅完全空串命中；
    - paas：``awk END{print NR}`` 为 0 ⇒ 仅 0 行文件命中（纯换行文件 NR≥1，
      属正常读取，见 ``test_whitespace_only_file_is_read_result``）。
    """
    backends = _make_backends(tmp_path, content)
    backend, _ = backends[backend_name]

    result = backend.read("f.txt")

    assert isinstance(result, str), f"{backend_name} 空文件应返回提示文案"
    assert "文件存在但内容为空" in result


@pytest.mark.parametrize(("backend_name", "content"), [("paas", "\n"), ("e2b", "\n")])
def test_whitespace_only_file_is_read_result(tmp_path, backend_name, content):
    """纯空白但非 0 字节：PaaS / E2B 按正常读取返回 ReadResult。

    这两族的「空」判据不含 ``strip()``，故 ``"\\n"`` 是合法的一行空内容。
    """
    backends = _make_backends(tmp_path, content)
    backend, _ = backends[backend_name]

    result = backend.read("f.txt")

    assert isinstance(result, ReadResult)
    assert "\n".join(result.lines).split("\n") == result.lines


@pytest.mark.parametrize("backend_name", _ALL_BACKENDS)
def test_read_segment_is_single_empty_line(tmp_path, backend_name):
    """片段为单个空串 ⇒ ``lines == [""]``，``start_line`` 仍是源码行号。"""
    backends = _make_backends(tmp_path, "a\n\nb")
    backend, _ = backends[backend_name]

    result = backend.read("f.txt", offset=1, limit=1)

    assert isinstance(result, ReadResult)
    assert result.lines == [""]
    _assert_read_contract(result, first_line=2)
    assert _render(result) == f"{2:>{LINE_NUMBER_WIDTH}}\t"


@pytest.mark.parametrize("backend_name", _ALL_BACKENDS)
def test_read_uses_split_not_splitlines(tmp_path, backend_name):
    """专门的 ``splitlines()`` 回归：``"x\\n\\n"`` 的空行必须留在结果里。

    ``"x\\n\\n".splitlines() == ["x", ""]``；``split("\\n") == ["x","",""]``。
    各族行模型不同（见 ``_expected_lines``），故断言「不短于 splitlines() 且
    保留末尾空行」这一**共同**不变量，而不是固定元素个数。
    """
    content = "x\n\n"
    backends = _make_backends(tmp_path, content)
    backend, _ = backends[backend_name]

    result = backend.read("f.txt")

    assert isinstance(result, ReadResult)
    assert result.lines[0] == "x"
    assert result.lines[-1] == ""
    # 不得比 splitlines() 更短（splitlines 会丢掉末尾那个空行）
    assert len(result.lines) >= len(content.splitlines())
    assert "\n".join(result.lines).split("\n") == result.lines


# ---------------------------------------------------------------------------
# offset / limit / start_line
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend_name", _ALL_BACKENDS)
@pytest.mark.parametrize(
    ("offset", "limit", "expected_lines", "expected_start"),
    [
        (0, 2000, ["a", "b", "c", "d", "e"], 1),
        (0, 2, ["a", "b"], 1),
        (2, 2, ["c", "d"], 3),
        (4, 2000, ["e"], 5),
        (2, 1, ["c"], 3),
    ],
)
def test_read_offset_limit_and_start_line(tmp_path, backend_name, offset, limit, expected_lines, expected_start):
    """``start_line`` 是原文件 1-based 行号；limit 截断；offset 不污染行号。"""
    # 该内容无尾换行 ⇒ 两种行模型一致，可直接比对固定期望值
    backends = _make_backends(tmp_path, "a\nb\nc\nd\ne")
    backend, _ = backends[backend_name]

    result = backend.read("f.txt", offset=offset, limit=limit)

    assert isinstance(result, ReadResult), f"{backend_name} 应返回 ReadResult"
    assert result.lines == expected_lines
    _assert_read_contract(result, first_line=expected_start)


@pytest.mark.parametrize("backend_name", _ALL_BACKENDS)
def test_read_non_zero_offset_keeps_trailing_blank_line(tmp_path, backend_name):
    """非零 offset 与末尾空行叠加：两者都要正确。"""
    content = "1\n2\n3\n\n"
    backends = _make_backends(tmp_path, content)
    backend, _ = backends[backend_name]

    result = backend.read("f.txt", offset=2)

    assert isinstance(result, ReadResult)
    expected = _expected_lines(backend_name, content)[2:]
    assert result.lines == expected
    # 末尾那个空行必须留着（splitlines() 会把 "3\n\n" 切成 ["3"]）
    assert result.lines[-1] == ""
    _assert_read_contract(result, first_line=3)


# ---------------------------------------------------------------------------
# 诊断 / 异常仍是各自原语义（契约只改「成功」路径）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend_name", ["local", "bwrap", "e2b", "paas", "mock"])
def test_read_offset_overflow_is_never_a_readresult(tmp_path, backend_name):
    """偏移越界不得伪装成成功结果。"""
    backends = _make_backends(tmp_path, "only")
    backend, _ = backends[backend_name]

    if backend_name == "paas":
        # PaaS 历史语义是抛异常（由 @_paas_error_enhance 包装）
        with pytest.raises(IndexError, match="exceeds file length"):
            backend.read("f.txt", offset=99)
        return

    result = backend.read("f.txt", offset=99)
    assert isinstance(result, str)
    assert "exceeds file length" in result


@pytest.mark.parametrize("backend_name", ["local", "bwrap", "e2b"])
def test_read_missing_file_is_diagnostic_string(tmp_path, backend_name):
    """缺文件是返回型诊断（str），不是 ReadResult。"""
    content = "irrelevant"
    backends = _make_backends(tmp_path, content)
    backend, _ = backends[backend_name]

    if backend_name == "bwrap":
        backend._read_text.return_value = None
    elif backend_name == "e2b":
        backend._ensure_sandbox = lambda: _DummyE2BSandbox(  # type: ignore[method-assign]
            files=MagicMock(exists=lambda _p: False)
        )

    result = backend.read("missing.txt")

    assert isinstance(result, str)
    assert "not found" in result


def test_read_never_accepts_transform_callback(tmp_path):
    """第一版的 ``transform`` 关键字参数已彻底移除（不留兼容路径）。"""
    import inspect

    for cls in (FilesystemBackend, E2BSandboxBackend, PaasSandboxBackend, RuntimeBackend):
        params = inspect.signature(cls.read).parameters
        assert "transform" not in params, f"{cls.__name__}.read 仍有 transform 参数"
