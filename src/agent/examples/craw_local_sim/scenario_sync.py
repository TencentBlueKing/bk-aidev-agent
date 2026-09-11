# -*- coding: utf-8 -*-
"""场景 2：agent --read/write--> craw（周期任务链路）。

在 agent 容器内执行 ``CrawSyncer.run_forever``：每周期 read（health）+
write（SOUL.md 写入共享的 craw workspace）+ 读回校验。全部周期通过打印
``SCENARIO-2 PASS``，否则非零码退出。
"""

import os
import sys
import time

from aidev_agent.packages.craw import CrawSyncer


def soul_provider() -> str:
    return (
        "# CRAW LOCAL SIM SOUL\n\n"
        f"synced_at: {time.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        "agent: craw-local-sim\n"
        "role: 你是本地模拟环境中的演示智能体。\n"
    )


def main() -> None:
    cycles = int(os.getenv("SIM_SYNC_CYCLES", "2"))
    syncer = CrawSyncer(soul_provider=soul_provider)
    print(f"backend={syncer.backend.name} home={syncer.home_dir} interval={syncer.interval}s cycles={cycles}")
    results = syncer.run_forever(max_cycles=cycles)
    for index, result in enumerate(results, 1):
        print(
            f"cycle {index}/{cycles}: ok={result.ok} health={result.health} "
            f"soul_bytes={result.soul_written_bytes} verified={result.soul_verified} error={result.error or '-'}"
        )
    assert all(r.ok and r.soul_verified for r in results), "存在失败周期"
    print("SCENARIO-2 PASS")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"SCENARIO-2 FAIL: {exc}")
        sys.exit(1)
