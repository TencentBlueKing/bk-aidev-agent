# -*- coding: utf-8 -*-
"""CrawSyncer：周期读写（health 打桩 + tmp_path 文件面）。"""

import pytest

from aidev_agent.packages.craw import CrawSyncer, OpenClawBackend


class _HealthStubBackend(OpenClawBackend):
    def __init__(self, ok=True):
        super().__init__(api_url="http://stub")
        self._ok = ok

    def health(self):
        return {"ok": self._ok, "status_code": 200 if self._ok else None, "latency_ms": 1.0, "backend": self.name}


class TestCrawSyncer:
    def test_run_cycle_writes_and_verifies_soul(self, tmp_path):
        syncer = CrawSyncer(
            backend=_HealthStubBackend(), home_dir=str(tmp_path), soul_provider=lambda: "# SOUL\nrole prompts"
        )
        result = syncer.run_cycle()
        assert result.ok and result.soul_verified
        assert (tmp_path / "SOUL.md").read_text(encoding="utf-8") == "# SOUL\nrole prompts"

    @pytest.mark.parametrize("ok, expected", [(True, True), (False, False)])
    def test_cycle_ok_follows_health(self, tmp_path, ok, expected):
        syncer = CrawSyncer(backend=_HealthStubBackend(ok=ok), home_dir=str(tmp_path))
        assert syncer.run_cycle().ok is expected

    def test_run_cycle_without_home_skips_file_side(self):
        syncer = CrawSyncer(backend=_HealthStubBackend(), soul_provider=lambda: "x")
        result = syncer.run_cycle()
        assert result.ok and result.soul_written_bytes == 0

    def test_run_forever_max_cycles(self, tmp_path):
        syncer = CrawSyncer(backend=_HealthStubBackend(), home_dir=str(tmp_path), interval=0.01)
        assert len(syncer.run_forever(max_cycles=2)) == 2

    def test_write_soul_without_home_raises(self):
        with pytest.raises(RuntimeError):
            CrawSyncer(backend=_HealthStubBackend()).write_soul("x")
