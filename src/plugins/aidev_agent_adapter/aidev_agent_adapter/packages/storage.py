"""安全文件、私有目录与文件锁公共工具。"""

import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def directory_fd(path: Path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def private_directory(path: Path) -> Path:
    path = path.absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("symlinked state path is not allowed")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_uid != os.getuid():
        raise ValueError("state directory must belong to the adapter user")
    path.chmod(0o700)
    return path


def write_private(path: Path, data: str | bytes) -> None:
    """以原子 0o600 权限及 O_NOFOLLOW 创建私有文件，避免先建再 chmod 的权限窗口。"""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data.encode("utf-8") if isinstance(data, str) else data)
        stream.flush()
        os.fsync(stream.fileno())


def open_lock_file(path: Path):
    """以 O_NOFOLLOW + 0o600 打开或创建排他锁文件。"""
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    return os.fdopen(fd, "a", encoding="utf-8")


@contextmanager
def open_private_log(path: Path):
    """以 O_NOFOLLOW + 0o600 打开进程私有日志文件。"""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        yield stream
