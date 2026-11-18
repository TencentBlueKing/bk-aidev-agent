"""file-kit 内运行的 Fork 字节门禁（仅标准库；不解包、不写源卷）。

按 tar 有效载荷计量：普通文件逻辑长度 + 软链长度，硬链 inode 只计一次，目录不计。
流式重新封装 tar，在转发每个文件前校验累计大小，目标卷不会接收超限文件数据。
这不是历史快照：源卷外部写者不受此脚本锁定，tar 读失败或复核失败均由调用方回滚。
"""

import os
import stat
import sys
import tarfile

TOO_LARGE = "AIDEV_FORK_COPY_TOO_LARGE"
BYTES_PREFIX = "AIDEV_FORK_SRC_BYTES="


class SizeLimitExceeded(Exception):
    def __init__(self, size):
        self.size = size
        super().__init__(f"PV payload exceeds byte limit: {size}")


def measure(root, max_bytes):
    total = 0
    seen = set()
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=_walk_error):
        for name in dirs + files:
            info = os.lstat(os.path.join(directory, name))
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)):
                continue
            inode = (info.st_dev, info.st_ino)
            if inode in seen:
                continue
            seen.add(inode)
            total += info.st_size
            if total > max_bytes:
                raise SizeLimitExceeded(total)
    return total


def _walk_error(error):
    raise error


def forward_tar(source, destination, max_bytes):
    total = 0
    with (
        tarfile.open(fileobj=source, mode="r|") as incoming,
        tarfile.open(fileobj=destination, mode="w|") as outgoing,
    ):
        for member in incoming:
            total += member.size if member.isfile() else len(os.fsencode(member.linkname)) if member.issym() else 0
            if total > max_bytes:
                raise SizeLimitExceeded(total)
            outgoing.addfile(member, incoming.extractfile(member) if member.isfile() else None)
    return total


def main():
    mode, limit, root = sys.argv[1:]
    try:
        if mode == "size":
            print(f"{BYTES_PREFIX}{measure(root, int(limit))}")
        elif mode == "copy":
            forward_tar(sys.stdin.buffer, sys.stdout.buffer, int(limit))
        else:
            raise ValueError(f"Unknown fork operation: {mode}")
    except SizeLimitExceeded as error:
        # copy 模式 stdout 是 tar 二进制流，业务标记只能写 stderr。
        print(f"{BYTES_PREFIX}{error.size}\n{TOO_LARGE}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
