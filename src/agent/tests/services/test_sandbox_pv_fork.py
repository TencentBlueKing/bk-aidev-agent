"""字节门禁使用小阈值等比验证，不代表个人环境 300MiB 接口压测。"""

import os
import shlex
import subprocess

import pytest

from aidev_agent.services import sandbox_pv_files as service
from aidev_agent.services.sandbox_pv_fork import SizeLimitExceeded, measure


@pytest.mark.parametrize("size", [1023, 1024, 1025])
def test_measure_boundary_ignores_directories_and_deduplicates_hardlinks(tmp_path, size):
    nested = tmp_path / "空 目录"
    nested.mkdir()
    payload = nested / "data"
    payload.write_bytes(b"x" * size)
    os.link(payload, nested / "hardlink")
    if size > 1024:
        with pytest.raises(SizeLimitExceeded):
            measure(tmp_path, 1024)
    else:
        assert measure(tmp_path, 1024) == size


@pytest.mark.parametrize("grows", [False, True])
def test_shell_tar_budget_rejects_growth_and_preserves_valid_tree(tmp_path, grows):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "data").write_bytes(b"x" * 128)
    (source / "link").symlink_to("data")
    script = service._fork_copy_script(1024).replace(service.FORK_SRC_MOUNT_PATH, str(source))
    script = script.replace(service.FORK_DST_MOUNT_PATH, str(target))
    growth_script = f"from pathlib import Path; Path({str(source / 'data')!r}).write_bytes(bytes(2048))"
    grow = "python3 -c " + shlex.quote(growth_script)
    wrapper = 'tar() { if [[ " $* " == *" -cf "* ]]; then ' + grow + '; fi; command tar "$@"; };\n'
    result = subprocess.run(["bash", "-c", (wrapper if grows else "") + script], capture_output=True, text=True)
    if grows:
        assert result.returncode != 0
        assert service._FORK_COPY_TOO_LARGE_MARKER in result.stderr
        assert service._FORK_COPY_DONE_MARKER not in result.stdout
        assert not (target / "data").exists()
    else:
        assert result.returncode == 0, result.stderr
        assert (target / "data").read_bytes() == b"x" * 128
        assert (target / "link").is_symlink()
